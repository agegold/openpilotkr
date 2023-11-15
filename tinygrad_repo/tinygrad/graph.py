import os, atexit
try:
  import networkx as nx  # type: ignore
except ImportError:
  nx = None # graph won't work
from collections import defaultdict
from typing import Dict, List
from tinygrad.ops import ScheduleItem, UnaryOps, BinaryOps, ReduceOps, MovementOps, LoadOps, BufferOps, TernaryOps, Op, OpType, LazyOp
from tinygrad.helpers import GRAPH, GRAPHPATH, DEBUG, GlobalCounters, getenv

# **** debugging and graphing ****

G = nx.DiGraph() if nx is not None else None
cnts: Dict[OpType, int] = defaultdict(int)
if DEBUG >= 2:
  def print_globalcounters():
    if GlobalCounters.time_sum_s == 0: return
    print(f"avg: {GlobalCounters.global_ops*1e-9/GlobalCounters.time_sum_s:8.2f} GFLOPS {GlobalCounters.global_mem*1e-9/GlobalCounters.time_sum_s:8.2f} GB/s",
          f"{' '*10}total: {GlobalCounters.kernel_count:5d} kernels {GlobalCounters.global_ops*1e-9:8.2f} GOPS {GlobalCounters.global_mem*1e-9:8.2f} GB {GlobalCounters.time_sum_s*1e3:8.2f} ms")
  atexit.register(print_globalcounters)
if GRAPH:
  def save_graph_exit():
    for k,v in cnts.items(): print(k, v)
    print("saving", G)
    nx.drawing.nx_pydot.write_dot(G, f'{GRAPHPATH}.dot')
    # -Gnslimit=100 can make it finish, but you won't like results
    os.system(f'dot -Tsvg {GRAPHPATH}.dot -o {GRAPHPATH}.svg')
  atexit.register(save_graph_exit)

node_count = 0
def nm(x):
  global node_count
  if not hasattr(x, 'node_id'):
    setattr(x, 'node_id', node_count)
    node_count += 1
  return x.node_id

def get_sop(op: List[Op]):
  op = [x for x in op if x not in BufferOps]
  if len(op) <= 2: return '.'.join([str(y).split(".")[1] for y in op][::-1])
  if len(op) <= 6: return '.'.join([str(y).split(".")[1][0:3] for y in op][::-1])
  return str(len(op))

def str_dtype(dtyp):
  ret = str(dtyp)[7:]
  return "" if ret == 'float' else f"\n{ret}"

logops = open(getenv("LOGOPS", ""),"a") if getenv("LOGOPS", "") else None
def log_schedule_item(si: ScheduleItem):
  if logops and si.ast.op not in LoadOps: logops.write(str(si.ast)+"\n")
  show_graph = bool(GRAPH)
  if not DEBUG and not show_graph: return
  if si.ast.op == LoadOps.CONTIGUOUS: setattr(si.out, 'node_id', nm(si.inputs[0].base))
  if si.ast.op in {LoadOps.CONST, LoadOps.CONTIGUOUS}: return

  op: List[Op] = [x.op for x in si.ast.get_lazyops()]
  oporder = [LoadOps, TernaryOps, ReduceOps, BinaryOps, UnaryOps, MovementOps, BufferOps]
  optype = type(sorted(op, key=lambda x: oporder.index(type(x)))[0])
  cnts[optype] += 1
  if show_graph:
    assert si.out.base == si.out, "all outputs based"
    top_colors = {LoadOps: '#FFFFa0', UnaryOps: "#c0c0c0", ReduceOps: "#8080ff", BinaryOps: "#c0c0c0", MovementOps: "#80ff80", TernaryOps: "#c0c0c0", BufferOps: '#FF8080'}
    for x in si.inputs:
      assert x.base == x, "all inputs based"
      #assert nm(x) in G.nodes, "all inputs seen"
      G.add_edge(nm(x), nm(si.out), label=get_sop(op), color='#00000060')
      if 'label' not in G.nodes[nm(x)]:
        G.nodes[nm(x)]['label'] = str(x.shape)+str_dtype(si.out.dtype)
    if nm(si.out) not in G.nodes: G.add_node(nm(si.out))

    G.nodes[nm(si.out)]['label'] = (str(set(x.shape for x in si.inputs))+"\n"+str(si.out.shape) if optype == ReduceOps else str(si.out.shape))+str_dtype(si.out.dtype)+(f"\n{si.ast.op}" if si.ast.op in LoadOps else "")
    G.nodes[nm(si.out)]['fillcolor'] = top_colors[optype]
    G.nodes[nm(si.out)]['color'] = 'black'
    G.nodes[nm(si.out)]['style'] = 'filled'

def _tree(lazydata, prefix=""):
  if type(lazydata).__name__ == "LazyBuffer": return [f"━━ realized {lazydata.dtype.name} {lazydata.shape}"] if (lazydata.realized) else _tree(lazydata.op, "LB ")
  if len(lazydata.src) == 0: return [f"━━ {prefix}{lazydata.op.name} {lazydata.arg if lazydata.arg else ''}"]
  lines = [f"━┳ {prefix}{lazydata.op.name} {lazydata.arg if lazydata.arg else ''}"]
  childs = [_tree(c) for c in lazydata.src[:]]
  for c in childs[:-1]: lines += [f" ┣{c[0]}"] + [f" ┃{l}" for l in c[1:]]
  return lines + [" ┗"+childs[-1][0]] + ["  "+l for l in childs[-1][1:]]

def print_tree(lazydata:LazyOp): print("\n".join([f"{str(i).rjust(3)} {s}" for i,s in enumerate(_tree(lazydata))]))