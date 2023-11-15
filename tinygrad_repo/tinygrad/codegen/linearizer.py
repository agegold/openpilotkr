from __future__ import annotations
from typing import List, Tuple, Any, Optional, cast, DefaultDict, NamedTuple, Dict, Union, Sequence, Final, Set
import itertools, math, functools
from collections import defaultdict
from enum import Enum, auto

from tinygrad.helpers import colored, ImageDType, DEBUG, dtypes, DType, prod, PtrDType, all_same
from tinygrad.ops import LazyOp, UnaryOps, ConstBuffer, MemBuffer, BufferOps
from tinygrad.ops import ReduceOps, BinaryOps, TernaryOps
from tinygrad.shape.shapetracker import ShapeTracker
from tinygrad.shape.symbolic import Variable, NumNode, VariableOrNum, Node, SumNode, MulNode, DivNode, ModNode, LtNode, AndNode, sym_rename
from tinygrad.codegen.optimizer import OptimizedKernel
from tinygrad.codegen.kernel import LocalBuffer
from tinygrad.lazy import vars_from_ast
from tinygrad.features.image import to_image_idx

# bottom ones are asm only
class UOps(Enum):
  LOOP = auto(); IF = auto(); END = auto(); SPECIAL = auto() # loops can be global, local, or other # noqa: E702
  DEFINE_GLOBAL = auto(); DEFINE_LOCAL = auto(); DEFINE_ACC = auto() # this defines buffers # noqa: E702
  LOAD = auto(); STORE = auto(); CONST = auto(); BARRIER = auto() # noqa: E702
  ALU = auto(); WMMA = auto(); CAST = auto(); GEP = auto() # noqa: E702

class UOp(NamedTuple):
  uop: UOps
  dtype: Optional[DType]
  vin: Tuple[UOp, ...]
  arg: Any
  def __repr__(self): return f"{self.num:4d} {str(self.uop):20s}: {str(self.dtype) if self.dtype is not None else '':25s} {str([x.num for x in self.vin]):32s} {self.arg}"
  #def __repr__(self): return f"{str(self.uop):20s}: {str(self.dtype) if self.dtype is not None else '':25s} {str(self.vin):32s} {self.arg}"

  # UOps are unique
  num: int
  def __hash__(self): return self.num
  def __eq__(self, x): return self.num == x.num

def get_grouped_dims(prefix, start_dim, local_dims, maxdim:int=0):
  local_idxs = loop_local_idxs = [Variable(f"{prefix}{start_dim+i}", 0, s-1) for i,s in enumerate(local_dims[0:maxdim-1] + (prod(local_dims[maxdim-1:]),) if len(local_dims) > maxdim else local_dims)]
  if maxdim != 0 and len(local_dims) > maxdim:
    dd = local_idxs[maxdim-1]
    nli = []
    for s in local_dims[maxdim-1:][::-1]:
      nli.append(dd % s)
      dd //= s
    local_idxs = local_idxs[0:maxdim-1] + nli[::-1]
  return local_idxs, [x for x in loop_local_idxs if not isinstance(x, NumNode)]

class Linearizer(OptimizedKernel):
  def uop_alu_idx(self, a:UOp, b, ops, ctx:Linearizer, op, dtype=dtypes.int32):
    render_b:UOp = cast(UOp, (NumNode(b) if not isinstance(b, Node) else b).render(ops, ctx))
    return self.uop(UOps.ALU, dtype, (a, render_b), op)
  def const(self, b:Union[int,float], dtype=dtypes.int32) -> UOp: return self.uop(UOps.CONST, dtype, tuple(), b)

  render_ops: Any = { Variable: lambda self, ops, ctx: ctx.loop_uops[self.expr], NumNode: lambda self, ops, ctx: ctx.const(self.b),
                MulNode: lambda self, ops, ctx: ctx.uop_alu_idx(self.a.render(ops, ctx), self.b, ops, ctx, BinaryOps.MUL),
                DivNode: lambda self, ops, ctx: ctx.uop_alu_idx(self.a.render(ops, ctx), self.b, ops, ctx, BinaryOps.DIV),
                ModNode: lambda self, ops, ctx: ctx.uop_alu_idx(self.a.render(ops, ctx), self.b, ops, ctx, BinaryOps.MOD),
                LtNode: lambda self, ops, ctx: ctx.uop_alu_idx(self.a.render(ops, ctx), self.b, ops, ctx, BinaryOps.CMPLT, dtype=dtypes.bool),
    SumNode: lambda self,ops,ctx: functools.reduce(lambda a,b: ctx.uop_alu_idx(a, b, ops, ctx, BinaryOps.ADD), self.nodes[1:], self.nodes[0].render(ops,ctx)),
    AndNode: lambda self,ops,ctx: functools.reduce(lambda a,b: ctx.uop_alu_idx(a, b, ops, ctx, BinaryOps.MUL, dtype=dtypes.bool), self.nodes[1:], self.nodes[0].render(ops,ctx)) }

  def global_load(self, i:int, idxs:Sequence[Node], acc=None) -> List[UOp]:
    const = self.bufs[i].val if isinstance(self.bufs[i], ConstBuffer) else acc

    def rename_var(v: VariableOrNum, expr: str): return v if isinstance(v, NumNode) else Variable(expr, v.min, v.max)

    amt, dim = 1, None
    upcast_dim = self.get_upcast_dim(i)
    if len(upcast_dim) == 1 and len(float4_expand := idxs[upcast_dim[0]].expand()) in [4,2]:
      dim, amt = upcast_dim[0], len(float4_expand)

    expand_vars = tuple([rename_var(idx.expand_idx(), f"_uidx{j}") for j, idx in enumerate(idxs)])
    fake_idxs = [idx.substitute({idx.expand_idx(): ev}) for idx, ev in zip(idxs, expand_vars)]
    if dim is not None:
      g_idx, g_valid = self.sts[i].expr_idxs(fake_idxs[:dim] + [float4_expand[0]] + fake_idxs[dim+1:])
      if (g_idx // amt * amt).render() != g_idx.render():
        (g_idx, g_valid), amt, dim = self.sts[i].expr_idxs(fake_idxs), 1, None
    else:
      g_idx, g_valid = self.sts[i].expr_idxs(fake_idxs)
    localtype = dtypes.float32 if amt == 1 else dtypes._float4 if amt == 4 else dtypes._float2

    e_idxs, e_valids = g_idx.expand(expand_vars), g_valid.expand(expand_vars)

    ret = []
    invalid_value = 0 if dtypes.is_int(self.bufs[i].dtype) else 0.0
    for idx, valid, rep_idx in zip(e_idxs, e_valids, Node.iter_idxs(expand_vars)):
      this_const, idx, valid = (invalid_value, Variable.num(0), Variable.num(1)) if valid.max == 0 else (const, idx, valid)
      key = f"{acc}{localtype}{this_const if this_const is not None and acc is None else (self.bufs[i].idx if isinstance(self.bufs[i], MemBuffer) else self.bufs[i].name)}{idx.render()}{valid.render()}"
      if key not in self.load_cache:
        if acc is not None:
          assert valid.min == 1
          self.load_cache[key] = self.uop(UOps.DEFINE_ACC, localtype, (), this_const, cachable=False)
        elif this_const is not None:
          self.load_cache[key] = self.const(this_const, localtype)
          if valid.min == 0 and valid.max == 1:
            valid_rendered = valid.render(self.render_ops, self)
            self.load_cache[key] = self.uop(UOps.ALU, localtype, (valid_rendered, self.load_cache[key], self.const(invalid_value, localtype)), TernaryOps.WHERE)
        else:
          buf_uop = self.buf_uops[i]
          assert buf_uop is not None, f"buffer {i} wasn't UOped"
          if isinstance(self.bufs[i].dtype, ImageDType):
            idx, valid = to_image_idx(self.bufs[i].dtype.shape, idx, valid)
            rendered_idx = self.uop(UOps.CAST, dtypes._int2, (idx[0].render(self.render_ops, self), idx[1].render(self.render_ops, self)))
          else:
            rendered_idx = idx.render(self.render_ops, self)

          if valid.min == 0:
            valid_rendered = valid.render(self.render_ops, self)
            self.load_cache[key] = self.uop(UOps.LOAD, localtype, (buf_uop, rendered_idx, valid_rendered, self.const(invalid_value, localtype)))
          else:
            self.load_cache[key] = self.uop(UOps.LOAD, localtype, (buf_uop, rendered_idx))
      ret.append(self.uop(UOps.GEP, dtypes.float32, (self.load_cache[key],), rep_idx[dim]) if dim is not None else self.load_cache[key])
    return ret

  def global_store(self, i:int, idxs:List[Node], store:List[UOp]) -> None:
    buf_uop = self.buf_uops[i]
    assert buf_uop is not None, f"buffer {i} wasn't UOped"

    expanded_nodes = [idx.expand() for idx in idxs]
    _idxs = [x[::-1] for x in itertools.product(*expanded_nodes[::-1])]
    store_offset = dict(zip(_idxs, store))

    # float4 grouping
    upcast_dim = self.get_upcast_dim(i)
    if len(upcast_dim) == 1 and len(expanded_nodes[upcast_dim[0]]) in [2,4]:
      grouped_store_offset = defaultdict(list)
      for k in store_offset:
        _idx = k[:upcast_dim[0]] + (expanded_nodes[upcast_dim[0]][0],) + k[upcast_dim[0]+1:]
        grouped_store_offset[_idx].append(store_offset[k])
      store_offset_new = {}
      for k,out_tokens in grouped_store_offset.items():
        amt = len(out_tokens)
        idx, valid = self.sts[i].expr_idxs(k)
        assert idx.render() == ((idx//amt)*amt).render(), "float4 stores are always aligned"
        assert valid.min == 1, "stores are always valid"
        store_offset_new[k] = self.uop(UOps.CAST, dtypes._float4 if amt == 4 else dtypes._float2, tuple(out_tokens))
      store_offset = store_offset_new

    for idx, var in store_offset.items():
      idx, valid = self.sts[i].expr_idxs(idx)
      if isinstance(self.bufs[i].dtype, ImageDType):
        idx, valid = to_image_idx(self.bufs[i].dtype.shape, idx, valid)
        rendered_idx = self.uop(UOps.CAST, dtypes._int2, tuple(x.render(self.render_ops, self) for x in idx))
      else:
        rendered_idx = idx.render(self.render_ops, self)
      self.uop(UOps.STORE, None, (buf_uop, rendered_idx, var))

  kernel_cnt: Final[DefaultDict[str, int]] = defaultdict(int)
  def linearize(self):
    # global uop cache
    self.saved_exprs: Dict[Tuple, UOp] = dict()

    # limit dims if we need to
    # TODO: broken, and doesn't really belong here
    #if self.opts.global_max and self.opts.local_max: self.limit_dims_to_max(self.opts.global_max, self.opts.local_max)

    # uops
    self.uops: List[UOp] = []
    self.buf_uops: List[Optional[UOp]] = [None]*len(self.bufs)
    self.loop_uops: Dict[str, UOp] = {}

    # add global buffers
    for i,buf in enumerate(self.bufs):
      if isinstance(buf, MemBuffer):
        self.buf_uops[i] = self.uop(UOps.DEFINE_GLOBAL, PtrDType(buf.dtype) if not isinstance(buf.dtype, ImageDType) else buf.dtype, (), (f"data{buf.idx}", buf.dtype))
    # add var vals
    for var in sorted(vars_from_ast(self.ast), key=lambda k: k.key):
      assert var.expr is not None
      self.loop_uops[var.expr] = self.uop(UOps.DEFINE_GLOBAL, dtypes.int32, (), (var.expr, dtypes._arg_int32))
    # define local buffers
    for lb in self.local_alias.values():
      self.buf_uops[self.bufs.index(lb)] = self.uop(UOps.DEFINE_LOCAL, PtrDType(dtypes.float32), (), (lb.name, self.sts[self.bufs.index(lb)].size()))
    # add a local buffer for multistage reduce. # TODO: use local alias
    if self.group_for_reduce:
      # TODO: the strides of this can be controlled
      self.sts.append(ShapeTracker.from_shape(tuple([1] * self.global_dims + list(self.full_shape[self.global_dims:self.global_dims+self.local_dims+len(self.group_for_reduce)]) + [1] * (self.shape_len - self.upcasted - len(self.group_for_reduce) - self.first_reduce) + [x[0] for x in self.upcasted_axis(0)])))
      self.bufs.append(LocalBuffer("temp", self.sts[-1].size()))
      self.buf_uops.append(self.uop(UOps.DEFINE_LOCAL, PtrDType(dtypes.float32), (), ("temp", self.sts[-1].size())))

    # print
    if DEBUG >= 4: self.printbufs()

    # kernel name (before late upcast)
    self.function_name = ("r_" if self.reduceop else "E_") + '_'.join([str(x) if isinstance(x, int) else sym_rename(x) for x in self.full_shape])
    self.display_name = ("r_" if self.reduceop else "E_") + colored('_', 'BLACK').join([colored(str(x), c) for x,c in zip(self.full_shape, self.colors())])

    # name the function something unique
    Linearizer.kernel_cnt[self.function_name] += 1
    suffix = f"{'n'+str(Linearizer.kernel_cnt[self.function_name]-1)}" if Linearizer.kernel_cnt[self.function_name] > 1 else ""
    self.function_name, self.display_name = self.function_name+suffix, self.display_name+colored(suffix, 'BLACK')

    # define indexes
    global_idxs, loop_global_idxs = get_grouped_dims("gidx", 0, self.full_shape[:self.global_dims], 3 if self.opts.has_local else 0)
    local_idxs, loop_local_idxs = get_grouped_dims("lidx", self.global_dims, self.full_shape[self.global_dims:self.first_reduce+len(self.group_for_reduce)], 3 if self.opts.has_local else 0)
    full_upcast_idxs = [Variable(None, 0, s-1) for s in self.full_shape[self.shape_len-self.upcasted:]]
    upcast_idxs = [Variable(None, 0, s-1) for s in self.output_shape[self.shape_len-self.upcasted:]]

    # global and local loops
    def render_loop(xx:List[Variable]):
      self.loop_uops.update({x.expr:self.uop(UOps.LOOP, dtypes.int32, (
        self.const(x.min) if isinstance(x.min, int) else cast(Node, x.min).render(self.render_ops, self),
        self.const(x.max+1) if isinstance(x.max, int) else cast(Node, x.max+1).render(self.render_ops, self)), cachable=False) for x in xx if not isinstance(x, NumNode) and x.expr is not None})
    def end_loop(xx:List[Variable]):
      for x in xx[::-1]:
        if not isinstance(x, NumNode) and x.expr is not None:
          loop_uop = self.loop_uops[x.expr]
          if loop_uop.uop == UOps.LOOP: self.uop(UOps.END, None, (loop_uop,))

    if self.dont_use_locals:
      self.global_size = [x.max+1 for x in loop_global_idxs][::-1]
      self.loop_uops.update({x.expr:self.uop(UOps.SPECIAL, dtypes.int32, (), (len(loop_global_idxs)-1-i, x.expr.replace("gidx", "idx"), x.max+1)) for i,x in enumerate(loop_global_idxs)})
    elif self.opts.has_local:
      self.global_size, self.local_size = [x.max+1 for x in loop_global_idxs][::-1], [x.max+1 for x in loop_local_idxs][::-1]
      self.global_size += [1]*(3-len(self.global_size))
      self.local_size += [1]*(3-len(self.local_size))
      self.loop_uops.update({x.expr:self.uop(UOps.SPECIAL, dtypes.int32, (), (len(loop_global_idxs)-1-i, x.expr, x.max+1)) for i,x in enumerate(loop_global_idxs)})
      self.loop_uops.update({x.expr:self.uop(UOps.SPECIAL, dtypes.int32, (), (len(loop_local_idxs)-1-i, x.expr, x.max+1)) for i,x in enumerate(loop_local_idxs)})
    else:
      render_loop(loop_global_idxs+loop_local_idxs)

    # parse AST
    loaded_buffers = {}
    acc = []
    self.load_cache: Dict[str, UOp] = {}
    if_gate: Optional[UOp] = None

    # reduce op
    fake_reduce_idxs = []
    if self.reduceop is not None:
      # define indexes
      reduce_idxs = [Variable(f"ridx{i}", 0, self.full_shape[i]-1) for i in range(self.first_reduce+len(self.group_for_reduce), self.shape_len-self.upcasted)]
      fake_reduce_idxs = [x*0 for x in reduce_idxs]

      # define accumulator
      acc = self.global_load(0, global_idxs+local_idxs+fake_reduce_idxs+upcast_idxs, {ReduceOps.SUM: 0.0, ReduceOps.MAX: -math.inf}[cast(ReduceOps, self.reduceop.op)])

      # reduce loop
      render_loop(reduce_idxs)

      # barrier for fast GEMM
      if self.use_tensor_cores: self.uop(UOps.BARRIER, None, (), cachable=False)

      # compute local aliases
      # TODO: this is garbage code and should be at least moved elsewhere
      locals_to_store = []
      for i in self.local_alias:
        localbuf_idx = self.bufs.index(self.local_alias[i])
        strides = self.sts[i].real_strides()
        extra_locals = [lidx for lidx,st in zip(local_idxs[self.exclude_local_upcast:], strides[len(global_idxs)+self.exclude_local_upcast:self.first_reduce]) if st == 0]
        this_upcast_idxs: List[Node] = []
        # TODO: just flipping the order here is likely not generic at all
        for j,v in list(enumerate(full_upcast_idxs))[::-1] if self.reverse_upcast_dir else list(enumerate(full_upcast_idxs)):
          if strides[len(global_idxs)+len(local_idxs)+len(reduce_idxs)+j] == 0:
            if DEBUG >= 4: print(f"upcasting@{j} stride 0")
            this_upcast_idxs.append(Variable.num(0))
          elif (elc:=[el for el in extra_locals if v.min == el.min and v.max == el.max]):
            if DEBUG >= 4: print(f"upcasting@{j} matched stride {elc[0]}")
            this_upcast_idxs.append(elc[0])
            extra_locals.remove(elc[0])
          elif (elc:=[el for el in extra_locals if v.min == el.min and (v.max+1)%(el.max+1) == 0]):
            tacc = Variable.num(0)
            rem = v.max+1
            while len(elc) and rem%(elc[0].max+1) == 0:
              if DEBUG >= 4: print(f"upcasting@{j} partial stride {rem} {elc[0]} left: {elc[1:]}")
              rem = rem//(elc[0].max+1)
              tacc += (elc[0] * rem)
              extra_locals.remove(elc[0])
              elc = [el for el in extra_locals if v.min == el.min and rem%(el.max+1) == 0]
            if DEBUG >= 4 and rem > 1: print(f"failed upcasting@{j} partial stride {rem} extra locals {extra_locals}")
            this_upcast_idxs.append(tacc + Variable(None, 0, rem-1))
          else:
            if DEBUG >= 4: print(f"failed upcasting@{j} stride {v} extra locals {extra_locals}")
            this_upcast_idxs.append(v)
        idxs = global_idxs+local_idxs+reduce_idxs+(this_upcast_idxs[::-1] if self.reverse_upcast_dir else this_upcast_idxs)
        idxs = [idx*0 if s == 0 else idx for idx,s in zip(idxs,strides)]
        if DEBUG >= 3: print(f"{localbuf_idx} alias {i}:", idxs)
        ll = self.global_load(i, idxs)
        locals_to_store.append((localbuf_idx, idxs, ll))

      # copy in any global buffers
      if self.use_tensor_cores:
        if self.opts.device == "METAL":
          if 2 * len(acc) == len(locals_to_store[0][2]) * len(locals_to_store[1][2]):
            i = 0
            for y0,y1 in zip(locals_to_store[1][2][::2], locals_to_store[1][2][1::2]):
              for x0,x1 in zip(locals_to_store[0][2][::2], locals_to_store[0][2][1::2]):
                self.uop(UOps.WMMA, None, (x0, x1, y0, y1, acc[i], acc[i+1]), ("METAL",))
                i += 2
          else:
            k = len(locals_to_store[1][2]) // 2
            for i in range(0, len(acc), 2):
              for y0,y1,x0,x1 in zip(locals_to_store[1][2][:k], locals_to_store[1][2][k:], locals_to_store[0][2][k*i:], locals_to_store[0][2][k*i+k:]):
                self.uop(UOps.WMMA, None, (x0, x1, y0, y1, acc[i], acc[i+1]), ("METAL",))
        elif self.opts.device == "HIP":
          i = 0
          for y in range(0, len(locals_to_store[1][2]), 0x10):
            for x in range(0, len(locals_to_store[0][2]), 0x10):
              self.uop(UOps.WMMA, None, tuple(locals_to_store[0][2][x:x+0x10]+locals_to_store[1][2][y:y+0x10]+acc[i:i+8]), ("HIP",))
              i += 8
      else:
        if locals_to_store:
          self.uop(UOps.BARRIER, None, (), cachable=False)
          for i, idxs, ll in locals_to_store: self.global_store(i, idxs, ll)
          self.uop(UOps.BARRIER, None, (), cachable=False)

        # load earlybufs
        loaded_buffers.update({b:self.global_load(self.bufs.index(self.local_alias[i]) if i in self.local_alias else i, global_idxs+local_idxs+reduce_idxs+full_upcast_idxs) for i,b in enumerate(self.bufs[1:], start=1) if b in self.earlybufs})

        # run early AST (with reduce)
        self.ast_parse(self.reduceop, [acc[off] for off in self.acc_offsets(self.full_buf_index)], loaded_buffers, do_reduce=True)

      # end the reduce loop
      end_loop(reduce_idxs)
      self.load_cache.clear()

      # end the local loop, do the local reduce
      if self.group_for_reduce:
        fake_global_idxs = [x*0 for x in global_idxs]
        self.global_store(-1, fake_global_idxs+local_idxs+fake_reduce_idxs+upcast_idxs, acc)  # store accumulators
        self.uop(UOps.BARRIER, None, (), cachable=False)
        end_loop(loop_local_idxs)  # TODO: this is ending too much, should only end what's in the if?
        if self.opts.has_local:
          fake_idxs = [Variable.num(0)]*len(self.sts[-1].shape)
          fake_idxs[self.global_dims+self.local_dims:self.global_dims+len(local_idxs)] = local_idxs[self.local_dims:]
          if_cond: UOp = (self.sts[-1].expr_idxs(fake_idxs)[0]<1).render(self.render_ops, self)
          if_gate = self.uop(UOps.IF, None, (if_cond,), cachable=False)

        # create new late reduce local loops and replace local_idxs that have been used
        end_local_idxs = [Variable(f"tidx{i}", 0, self.full_shape[i]-1 if i >= self.first_reduce and i not in self.upcast_in_mid_reduce_axes else 0) for i in range(0, self.first_reduce+len(self.group_for_reduce))]
        local_idxs = local_idxs[:self.local_dims] + end_local_idxs[self.global_dims + self.local_dims:]

        # if any group_for_reduce items aren't reduces, upcast them here
        for j in self.upcast_in_mid_reduce_axes:
          self.reshape_and_permute(None, [i for i in range(self.shape_len) if i != j] + [j])
          self.upcast()
          self.group_for_reduce.pop()
          local_idxs = local_idxs[:-1]
          end_local_idxs = end_local_idxs[:-1]
          # regenerate upcast_idxs
          upcast_idxs = [Variable(None, 0, s-1) for s in self.output_shape[self.shape_len-self.upcasted:]]

        # NOTE: this structure is the same as the reduce op above

        # define late accumulator
        acc = self.global_load(-1, fake_global_idxs+local_idxs+fake_reduce_idxs+upcast_idxs, {ReduceOps.SUM: 0.0, ReduceOps.MAX: -math.inf}[cast(ReduceOps, self.reduceop.op)])

        # late reduce loop
        render_loop(end_local_idxs)

        # load localbufs
        loaded_buffers["LOCAL_BUFFER"] = self.global_load(-1, fake_global_idxs+local_idxs+fake_reduce_idxs+upcast_idxs)

        # there's no AST here (and there's no shape for the reduce LazyOp)
        self.ast_parse(LazyOp(self.reduceop.op, ("LOCAL_BUFFER",)), [acc[off] for off in self.acc_offsets(-1)], loaded_buffers, do_reduce=True) # type: ignore

        # end the late reduce loop
        end_loop(end_local_idxs)
        self.load_cache.clear()

    # load latebufs
    loaded_buffers.update({b:self.global_load(i, global_idxs+local_idxs+fake_reduce_idxs+upcast_idxs) for i,b in enumerate(self.bufs) if b not in self.earlybufs and i != 0 and b.__class__ is not LocalBuffer})

    # run late AST
    val = self.ast_parse(self.ast, acc, loaded_buffers)

    # store
    self.global_store(0, global_idxs+local_idxs+fake_reduce_idxs+upcast_idxs, val)

    # end the global (and maybe local) loop
    if if_gate: self.uop(UOps.END, None, (if_gate,))
    end_loop(loop_global_idxs+loop_local_idxs if not self.group_for_reduce else loop_global_idxs)

    # (recursively) remove childless uops
    UOPS_W_SIDE_EFFECTS = {UOps.STORE, UOps.WMMA, UOps.END, UOps.BARRIER, UOps.DEFINE_GLOBAL}
    while 1:
      has_child: Set[UOp] = set()
      for ru in self.uops:
        for vu in ru.vin:
          has_child.add(vu)
      nu: List[UOp] = [x for x in self.uops if x in has_child or x.uop in UOPS_W_SIDE_EFFECTS]
      if len(nu) == len(self.uops): break
      if DEBUG >= 4: print(f"reduced UOp count from {len(self.uops)} to {len(nu)}")
      self.uops = nu

    return self

  def uop(self, uop:UOps, dtype:Optional[DType], vin:Tuple[UOp, ...], arg:Any=None, cachable=True) -> UOp:
    key = (uop, dtype, vin, arg)
    if uop == UOps.STORE and len(vin) == 2 and vin[0] == vin[1]: return vin[0]   # self store is noop
    if uop == UOps.CAST and all(x.uop == UOps.GEP for x in vin) and all_same([x.vin[0] for x in vin]) and all(x.arg == i for i,x in enumerate(vin)): return vin[0].vin[0]
    if uop == UOps.GEP and vin[0].uop == UOps.CONST: return self.const(vin[0].arg, dtype)
    if uop == UOps.ALU:
      # rewrites. NOTE: the rewritten NEG op is still around...
      if arg == BinaryOps.ADD and vin[1].uop == UOps.ALU and vin[1].arg == UnaryOps.NEG: return self.uop(UOps.ALU, dtype, (vin[0], vin[1].vin[0]), BinaryOps.SUB, cachable=cachable)
      # constant folding
      if arg == UnaryOps.NEG and vin[0].uop == UOps.CONST: return self.const(-vin[0].arg, dtype)
      # zero folding
      for x in [0,1]:
        if arg == BinaryOps.ADD and vin[x].uop == UOps.CONST and vin[x].arg == 0.0: return vin[1-x]
        if arg == BinaryOps.MUL and vin[x].uop == UOps.CONST and vin[x].arg == 1.0: return vin[1-x]
        if arg == BinaryOps.MUL and vin[x].uop == UOps.CONST and vin[x].arg == 0.0: return vin[x]
      if arg == BinaryOps.SUB and vin[1].uop == UOps.CONST and vin[1].arg == 0.0: return vin[0]
      if arg == BinaryOps.DIV and vin[1].uop == UOps.CONST and vin[1].arg == 1.0: return vin[0]
    if cachable and key in self.saved_exprs: return self.saved_exprs[key]
    self.uops.append(UOp(uop, dtype, vin, arg, len(self.uops)))
    if DEBUG >= 5: print(self.uops[-1])
    if cachable: self.saved_exprs[key] = self.uops[-1]
    return self.uops[-1]

  def ast_parse(self, x, acc, loaded_buffers, do_reduce=False) -> List[UOp]:
    if x.__class__ is not LazyOp: return loaded_buffers[x]    # for LOCAL_BUFFER
    if x.op in BufferOps: return loaded_buffers[x.arg]
    if x.op in [UnaryOps.NOOP, UnaryOps.CAST]: return self.ast_parse(x.src[0], acc, loaded_buffers)  # cast isn't an ALU op
    if x.op in ReduceOps and not do_reduce: return acc
    # MULACC fusion. TODO: this is copied from Interpreted
    if x.op == ReduceOps.SUM and x.src[0].__class__ is LazyOp and x.src[0].op == BinaryOps.MUL:
      x = LazyOp(TernaryOps.MULACC, x.src[0].src, x.arg)
    if x.op == ReduceOps.SUM and x.src[0].__class__ is LazyOp and x.src[0].op == UnaryOps.CAST and x.src[0].src[0].__class__ is LazyOp and x.src[0].src[0].op == BinaryOps.MUL:
      x = LazyOp(TernaryOps.MULACC, x.src[0].src[0].src, x.arg)
    values = [self.ast_parse(v, acc, loaded_buffers) for v in x.src]
    ops = {ReduceOps.SUM:BinaryOps.ADD, ReduceOps.MAX:BinaryOps.MAX, TernaryOps.MULACC:TernaryOps.MULACC}
    if x.op in ops:
      ret = [(idx, self.uop(UOps.STORE, dtypes.float32, (val[-1], self.uop(UOps.ALU, dtypes.float32, val, ops[x.op], cachable=False)))) for idx, val in zip([[i] for i in range(len(values[0]))], zip(*values, acc))]
    else:
      ret = [(idx, self.uop(UOps.ALU, dtypes.float32, val, x.op)) for idx, val in zip([[i] for i in range(len(values[0]))], zip(*values))]
    ordered_ret: List[Optional[UOp]] = [None]*len(values[0])
    # scatter
    for i,j in ret:
      for k in i:
        ordered_ret[k] = j
    assert all(isinstance(x, UOp) for x in ordered_ret), "some tokens didn't get scattered?"
    return cast(List[UOp], ordered_ret)
