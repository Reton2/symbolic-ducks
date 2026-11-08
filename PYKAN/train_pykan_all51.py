"""Train a pykan KAN on ALL 51 inputs and extract a symbolic equation.

pykan 0.2.x:  pip install pykan

    python train_pykan_all51.py --target alloc --device cuda
    python train_pykan_all51.py --target halt  --device cuda
    python train_pykan_all51.py --target tier  --device cuda

Targets:
    alloc : allocation fraction (0-1)
    halt  : 1 if EMERGENCY_HALT else 0  (threshold the score)
    tier  : urgency tier 0-3            (round the score)
"""
import argparse
import importlib.metadata
import re
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sympy as sp
import torch
from sklearn.model_selection import train_test_split
from sympy.printing.numpy import NumPyPrinter

from kan import KAN

# ----------------------------------------------------------------------------
# Args
# ----------------------------------------------------------------------------
ap = argparse.ArgumentParser()
ap.add_argument("--csv", default="dag_samples.csv")
ap.add_argument("--target", choices=["alloc", "halt", "suspend", "tier"], default="alloc")
ap.add_argument("--hidden", type=int, default=2, help="hidden nodes (0 = no hidden layer)")
ap.add_argument("--grid", type=int, default=5)
ap.add_argument("--steps", type=int, default=100)
ap.add_argument("--lamb", type=float, default=0.003, help="sparsity penalty (raise it for fewer terms)")
ap.add_argument("--edge_th", type=float, default=0.01, help="edge pruning threshold (lower keeps more edges)")
ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--ordinal_onehot", action="store_true",
                help="treat inp_o_* tier inputs as categories (one coefficient per level, no sin() on 4-level inputs)")
ap.add_argument("--lib", choices=["safe", "simple", "full"], default="safe",
                help="safe = x, x^2, tanh, abs ; simple adds sqrt, log ; full adds exp, sin, x^3, x^4")
ap.add_argument("--a_range", type=float, default=3.0,
                help="max |inner scale| for symbolic fits (10 allows sin(9x)-style overfits)")
args = ap.parse_args()

SEED = args.seed
torch.manual_seed(SEED)
np.random.seed(SEED)
device = torch.device(args.device)
print(f"pykan {importlib.metadata.version('pykan')} | device: {device}")

# ----------------------------------------------------------------------------
# Data + targets (same 80/20 split as the deep model)
# ----------------------------------------------------------------------------
df = pd.read_csv(args.csv)
directive = df["act_a_halt_algorithm_directive"].map(
    {"CONTINUE_TRADING": 0, "SUSPEND_NEW_ORDERS": 1, "EMERGENCY_HALT": 2})
assert not directive.isna().any(), "Unmapped directive values"

if args.target == "alloc":
  y = (df["act_a_execute_block_allocation_pct"].values / 100.0).astype("float32")
elif args.target == "halt":
  y = (directive.values == 2).astype("float32")
elif args.target == "suspend":
  y = (directive.values >= 1).astype("float32")   # SUSPEND_NEW_ORDERS or EMERGENCY_HALT
else:
  y = df["act_a_liquidate_all_urgency_tier"].values.astype("float32")

idx_tr, idx_va = train_test_split(
    np.arange(len(df)), test_size=0.2, random_state=0, stratify=directive.values)

# ----------------------------------------------------------------------------
# Features: all inp_* columns. One-hot the nominal ones; standardize the rest.
# ----------------------------------------------------------------------------
inp_cols = [c for c in df.columns if c.startswith("inp_")]
cat_cols = [c for c in inp_cols if c.startswith("inp_c_")]
ord_cols = [c for c in inp_cols if c.startswith("inp_o_")]
enc_cols = cat_cols + (ord_cols if args.ordinal_onehot else [])
feats = pd.get_dummies(df[inp_cols], columns=enc_cols, dtype=float).astype("float32")
feats.columns = [re.sub(r"\W", "_", c) for c in feats.columns]   # valid sympy names
# Constant columns have zero range, which breaks pykan's spline grid (-> NaN)
const = [c for c in feats.columns if feats[c].iloc[idx_tr].nunique() < 2]
if const:
  print(f"Dropping {len(const)} constant input column(s): {const}")
  feats = feats.drop(columns=const)
selected = list(feats.columns)
print(f"{len(selected)} inputs")

# Min-max scale EVERY input to [-1, 1] using train data: z = (x - centre) / halfrange.
# This matches pykan's default grid range, so we can fit with update_grid=False
# (quantile-based grid updates produce NaN on binary / few-valued inputs).
Xraw = feats.values
lo, hi = Xraw[idx_tr].min(0), Xraw[idx_tr].max(0)
mu = ((hi + lo) / 2).astype("float32")          # centre
sd = ((hi - lo) / 2).astype("float32")          # half-range
Xs = ((Xraw - mu) / sd).astype("float32")
assert np.isfinite(Xs).all(), "Non-finite values in scaled inputs"

ds = {
    "train_input": torch.tensor(Xs[idx_tr]).to(device),
    "train_label": torch.tensor(y[idx_tr]).unsqueeze(1).to(device),
    "test_input": torch.tensor(Xs[idx_va]).to(device),
    "test_label": torch.tensor(y[idx_va]).unsqueeze(1).to(device),
}


# ----------------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------------
def report(pred, name):
  yt = y[idx_va]
  if args.target == "alloc":
    p = np.clip(pred, 0, 1)
    err = np.abs(p - yt)
    print(f"[{name}] allocation MAE {err.mean() * 100:.2f} pts | "
          f"p95 {np.percentile(err, 95) * 100:.2f} pts | max {err.max() * 100:.2f} pts")
  elif args.target in ("halt", "suspend"):
    for th in (0.5, 0.3):
      hit = pred >= th
      tp = int((hit & (yt == 1)).sum())
      fn = int((~hit & (yt == 1)).sum())
      fp = int((hit & (yt == 0)).sum())
      print(f"[{name}] threshold {th}: accuracy {(hit == (yt == 1)).mean():.3f} | "
            f"{args.target} recall {tp}/{tp + fn} | false alarms {fp}")
  else:
    p = np.clip(np.rint(pred), 0, 3)
    print(f"[{name}] tier accuracy {(p == yt).mean():.3f} "
          f"(majority baseline {np.bincount(yt.astype(int)).max() / len(yt):.3f})")


def predict_nn(model):
  with torch.no_grad():
    return model(ds["test_input"]).cpu().numpy().ravel()


# ----------------------------------------------------------------------------
# Train -> prune -> refit -> symbolic -> refit
# ----------------------------------------------------------------------------
width = [len(selected), args.hidden, 1] if args.hidden > 0 else [len(selected), 1]
model = KAN(width=width, grid=args.grid, k=3, seed=SEED, device=device)

print(f"\n[1/4] Training KAN {width} (sparsity lamb={args.lamb}) ...")
t0 = time.time()
model.fit(ds, opt="LBFGS", steps=args.steps, lamb=args.lamb, lamb_entropy=2.0, update_grid=False)
if not np.isfinite(predict_nn(model)).all():
  raise SystemExit("Training produced NaN. Try --lamb 0.005, --grid 3, or --device cpu.")
report(predict_nn(model), "dense KAN")

print("\n[2/4] Pruning and refitting ...")
try:
  try:
    model = model.prune(edge_th=args.edge_th)
  except TypeError:
    model = model.prune()
except Exception as e:
  print(f"  prune failed ({e}); continuing without pruning")
model.fit(ds, opt="LBFGS", steps=args.steps, lamb=0.0, update_grid=False)
report(predict_nn(model), "pruned KAN")

try:
  model(ds["train_input"])
  model.plot()
  plt.savefig(f"pykan_all51_{args.target}_plot.png", dpi=150, bbox_inches="tight")
  print(f"  saved pykan_all51_{args.target}_plot.png")
except Exception as e:
  print(f"  plot skipped ({e})")

print("\n[3/4] Symbolic regression on each remaining edge ...")
if args.lib == "safe":
  lib = ["x", "x^2", "tanh", "abs"]   # no log/sqrt: they can turn NaN during refit
elif args.lib == "simple":
  lib = ["x", "x^2", "sqrt", "log", "tanh", "abs"]
else:
  lib = ["x", "x^2", "x^3", "x^4", "exp", "log", "sqrt", "tanh", "sin", "abs"]
rng = (-args.a_range, args.a_range)
try:
  try:
    model.auto_symbolic(lib=lib, a_range=rng, b_range=rng)
  except TypeError:
    model.auto_symbolic(lib=lib)
except Exception as e:
  raise SystemExit(f"auto_symbolic failed: {e}\nIf this is a cuda/cpu mismatch, rerun with --device cpu.")

print("\n[4/4] Refitting affine parameters of the symbolic functions ...")
model.fit(ds, opt="LBFGS", steps=50, lamb=0.0, update_grid=False)
print(f"Total train time: {time.time() - t0:.1f}s")
nn_pred = predict_nn(model)
if not np.isfinite(nn_pred).all():
  raise SystemExit("Symbolic refit produced NaN (usually from log/sqrt). Rerun with --lib safe.")
report(nn_pred, "symbolic KAN")

# ----------------------------------------------------------------------------
# Extract the equation
# ----------------------------------------------------------------------------
z = [sp.Symbol(f"z_{n}") for n in selected]   # scaled inputs
x = [sp.Symbol(n) for n in selected]          # raw inputs

# Passing our own sympy symbols avoids pykan's exec()-based variable creation,
# which is broken on Python 3.13 (NameError: name 'x1' is not defined).
try:
  formulas, variables = model.symbolic_formula(var=z)
except NameError as e:
  raise SystemExit(f"symbolic_formula failed ({e}). This is the Python 3.13 exec() issue in pykan; "
                   "use a Python 3.11/3.12 runtime, or send me the traceback.")
expr = formulas[0]
expr_z = expr.xreplace(dict(zip(variables, z)))


def round_expr(e, nd=4):
  return e.xreplace({a: sp.Float(round(float(a), nd), nd + 1) for a in e.atoms(sp.Float)})


expr_z = round_expr(expr_z)
used = [s for s in z if expr_z.has(s)]
expr_raw = round_expr(expr_z.xreplace(
    {zi: (xi - float(m)) / float(s) for zi, xi, m, s in zip(z, x, mu, sd)}))

out_name = {"alloc": "allocation_fraction", "halt": "halt_score", "suspend": "suspend_score", "tier": "tier_score"}[args.target]
lines = [
    f"=== {out_name} equation ===",
    f"Inputs used by the equation: {len(used)} of {len(selected)}",
    "  " + ", ".join(str(s)[2:] for s in used),
    "",
    "Scaled form (z_i = (x_i - centre_i)/halfrange_i; each input maps to [-1, 1] on training data):",
    f"  {out_name} = {expr_z}",
    "",
    "Scaling constants (inputs used only):",
] + [f"  {n}: centre={float(m):.6g}, halfrange={float(s):.6g}"
     for n, m, s, zi in zip(selected, mu, sd, z) if expr_z.has(zi)] + [
    "",
    "Raw-input form:",
    f"  {out_name} = {expr_raw}",
    "",
]
if args.target == "alloc":
  lines.append("allocation_pct = 100 * clip(allocation_fraction, 0, 1)")
elif args.target == "halt":
  lines.append("EMERGENCY_HALT if halt_score >= 0.5  (a lower threshold raises recall)")
elif args.target == "suspend":
  lines.append("SUSPEND_NEW_ORDERS (or stronger) if suspend_score >= 0.5.\n"
               "Full directive: EMERGENCY_HALT if halt_score >= 0.5, else SUSPEND_NEW_ORDERS if suspend_score >= 0.5, else CONTINUE_TRADING")
else:
  lines.append("urgency_tier = clip(round(tier_score), 0, 3)")
text = "\n".join(lines)
print("\n" + text)
open(f"pykan_all51_equation_{args.target}.txt", "w").write(text)

code = NumPyPrinter().doprint(expr_raw)
src = (f"import numpy\n\n\ndef {out_name}({', '.join(str(s) for s in x)}):\n"
       f"    return {code}\n")
open(f"pykan_all51_equation_{args.target}.py", "w").write(src)

# ----------------------------------------------------------------------------
# Fidelity of the closed-form equation + speed
# ----------------------------------------------------------------------------
f_z = sp.lambdify(z, expr_z, "numpy")
cols = [Xs[idx_va][:, i] for i in range(len(selected))]
eq_pred = np.broadcast_to(np.asarray(f_z(*cols), dtype="float64"), (len(idx_va),))

print("\n=== Fidelity of the closed-form equation (validation set) ===")
print(f"max |equation - symbolic KAN| = {np.abs(eq_pred - nn_pred).max():.2e}")
report(eq_pred, "EQUATION")

row = [c[:1] for c in cols]
t0 = time.perf_counter()
for _ in range(2000):
  f_z(*row)
single_us = (time.perf_counter() - t0) / 2000 * 1e6
t0 = time.perf_counter()
for _ in range(50):
  f_z(*cols)
batch_us = (time.perf_counter() - t0) / 50 / len(idx_va) * 1e6
print(f"\nEquation speed (numpy): {single_us:.1f} us per single row, "
      f"{batch_us:.3f} us/row in a batch of {len(idx_va)}")
print(f"Saved: pykan_all51_equation_{args.target}.txt / .py")