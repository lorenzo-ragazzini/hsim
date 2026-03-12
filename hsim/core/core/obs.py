from abc import ABC
from typing import Any, Callable, Iterable, List, Optional, Union
import operator

from atom.api import Atom, Value, Event as AtomEvent


class _AtomStore(Atom):
    """Minimal atom container: a raw value slot + a fire-and-forget change event.

    Using ``AtomEvent`` (not ``Value``) as the notification path ensures every
    ``ObservableVariable.set()`` call notifies observers unconditionally —
    including when a mutable collection (SortedList, list, …) is mutated
    in-place and the same object reference is stored again.
    """
    val = Value()
    changed = AtomEvent()


# ---------------------------------------------------------------------------
# Observable — abstract base
# ---------------------------------------------------------------------------

class Observable(ABC):

    @property
    def value(self):
        return self._get_value()

    def _get_value(self):
        raise NotImplementedError

    def __call__(self):
        return self._get_value()

    def add_environment(self, env) -> None:
        self._env = env

    def link(self, event):
        raise NotImplementedError

    def unlink(self, event):
        raise NotImplementedError

    # ------------------------------------------------------------------ arithmetic
    def __add__(self, other: Any):      return ObservableExpression(operator.add, self, other)
    def __radd__(self, other: Any):     return self + other
    def __iadd__(self, other: Any):     self.set(self._get_value() + other); return self
    def __sub__(self, other: Any):      return ObservableExpression(operator.sub, self, other)
    def __rsub__(self, other: Any):     return ObservableExpression(operator.sub, other, self)
    def __isub__(self, other: Any):     self.set(self._get_value() - other); return self
    def __mul__(self, other: Any):      return ObservableExpression(operator.mul, self, other)
    def __rmul__(self, other: Any):     return self * other
    def __imul__(self, other: Any):     self.set(self._get_value() * other); return self
    def __truediv__(self, other: Any):  return ObservableExpression(operator.truediv, self, other)
    def __rtruediv__(self, other: Any): return ObservableExpression(operator.truediv, other, self)
    def __itruediv__(self, other: Any): self.set(self._get_value() / other); return self
    def __floordiv__(self, other: Any): return ObservableExpression(operator.floordiv, self, other)
    def __rfloordiv__(self, other: Any):return ObservableExpression(operator.floordiv, other, self)
    def __mod__(self, other: Any):      return ObservableExpression(operator.mod, self, other)
    def __rmod__(self, other: Any):     return ObservableExpression(operator.mod, other, self)
    def __pow__(self, other: Any):      return ObservableExpression(operator.pow, self, other)
    def __rpow__(self, other: Any):     return ObservableExpression(operator.pow, other, self)

    # ------------------------------------------------------------------ comparison
    def __eq__(self, other: Any):  return ObservableExpression(operator.eq, self, other)
    def __ne__(self, other: Any):  return ObservableExpression(operator.ne, self, other)
    def __lt__(self, other: Any):  return ObservableExpression(operator.lt, self, other)
    def __le__(self, other: Any):  return ObservableExpression(operator.le, self, other)
    def __gt__(self, other: Any):  return ObservableExpression(operator.gt, self, other)
    def __ge__(self, other: Any):  return ObservableExpression(operator.ge, self, other)

    # ------------------------------------------------------------------ boolean / bitwise
    def __and__(self, other: Any):  return ObservableExpression(operator.and_, self, other)
    def __rand__(self, other: Any): return ObservableExpression(operator.and_, other, self)
    def __or__(self, other: Any):   return ObservableExpression(operator.or_, self, other)
    def __ror__(self, other: Any):  return ObservableExpression(operator.or_, other, self)

    # ------------------------------------------------------------------ unary
    def __neg__(self): return ObservableExpression(operator.neg, self)
    def __pos__(self): return ObservableExpression(operator.pos, self)
    def __abs__(self): return ObservableExpression(operator.abs, self)

    # ------------------------------------------------------------------ shift (assignment shorthand)
    def __ishift__(self, other: Any):  self.set(other); return self
    def __ilshift__(self, other: Any): return self.__ishift__(other)
    def __irshift__(self, other: Any): return self.__ishift__(other)

    # ------------------------------------------------------------------ misc
    def __bool__(self):      return bool(self._get_value())
    def __hash__(self):      return hash(id(self))
    def __getitem__(self, key): return self._get_value()[key]

    def __len__(self):
        val = self._get_value()
        if val is None or not hasattr(val, '__len__'):
            return 0
        return len(val)

    @staticmethod
    def any(*predicate: 'Observable') -> 'ObservableExpression':
        return ObservableExpression(any, *predicate)

    @staticmethod
    def all(*predicate: 'Observable') -> 'ObservableExpression':
        return ObservableExpression(all, *predicate)

    def proxy(self, accessor: Any = None, attr_name: str = None) -> 'ObservableProxy':
        return ObservableProxy(self, accessor=accessor, attr_name=attr_name)


# ---------------------------------------------------------------------------
# ObservableVariable
# ---------------------------------------------------------------------------

class ObservableVariable(Observable):
    """A reactive variable backed by a nucleic/atom store.

    ``set()`` always notifies observers (via atom's ``AtomEvent``) regardless
    of whether the stored value object changes identity — which is critical for
    mutable collections like ``SortedList`` that are mutated in-place.
    """

    def __init__(self, initial: Any, env=None):
        self._store = _AtomStore()
        self._store.val = initial
        self._env = env
        self._link_handlers: dict = {}   # id(event) → atom observer function

    # ------------------------------------------------------------------ value access
    def _get_value(self):
        return self._store.val

    @property
    def value(self):
        return self._store.val

    @value.setter
    def value(self, v):
        self.set(v)

    def set(self, new_value):
        self._store.val = new_value
        self._store.changed = True   # AtomEvent — fire unconditionally

    def update(self, func):
        self.set(func(self._store.val))

    # ------------------------------------------------------------------ link / unlink
    def link(self, event):
        should_reset = event._should_reset_on_false

        def handler(change):
            if self._store.val:
                event.trigger()
            elif should_reset:
                event.reset()

        self._link_handlers[id(event)] = handler
        self._store.observe('changed', handler)
        # Mirror reaktiv Effect: check current value immediately
        if self._store.val:
            event.trigger()

    def unlink(self, event):
        handler = self._link_handlers.pop(id(event), None)
        if handler is not None:
            try:
                self._store.unobserve('changed', handler)
            except Exception:
                pass

    # ------------------------------------------------------------------ collection helpers
    def length(self) -> 'ObservableExpression':
        return ObservableExpression(len, self)

    def append(self, element):
        self._store.val.append(element)
        self._store.changed = True

    def add(self, other: Any):
        self._store.val.add(other)
        self._store.changed = True

    def pop(self, index=-1):
        popped = self._store.val.pop(index)
        self._store.changed = True
        return popped

    def remove(self, element):
        self._store.val.remove(element)
        self._store.changed = True

    def extend(self, iterable):
        val = self._store.val
        if hasattr(val, 'update'):
            val.update(iterable)          # SortedList / SortedKeyList
        elif hasattr(val, 'extend'):
            val.extend(iterable)
        else:
            self._store.val = val + list(iterable)
        self._store.changed = True

    def clear(self):
        val = self._store.val
        if hasattr(val, 'clear'):
            val.clear()
        else:
            self._store.val = None
        self._store.changed = True

    def __iter__(self):
        return iter(self._store.val)

    def __repr__(self):
        return f"{self._store.val} (ObsVar:{id(self)})"

    def __str__(self):
        return f"{self._store.val} (Obs)"


# ---------------------------------------------------------------------------
# ObservableExpression
# ---------------------------------------------------------------------------

class ObservableExpression(Observable):
    """A lazily-computed expression over one or more ``ObservableVariable`` inputs.

    The dependency graph is static: leaf ``ObservableVariable`` instances are
    collected once (on the first ``link()`` call) by walking the operand tree.
    Each ``link(event)`` subscribes that single handler to every leaf's atom
    ``changed`` event; on any leaf change the expression is recomputed and the
    linked event is triggered / reset.
    """

    def __init__(
        self,
        op: Callable,
        *operands: Union['ObservableVariable', 'ObservableExpression'],
        env=None,
    ):
        self._op = op
        self._operands = operands
        self._env = env
        self._link_handlers: dict = {}          # id(event) → (handler_fn, [leaves])
        self._leaves: Optional[List[ObservableVariable]] = None   # lazy cache

    # ------------------------------------------------------------------ compute
    def _compute(self):
        op = self._op
        if op is any or op is all:
            # operands may be (list_of_items,) or multiple positional items
            items = (
                self._operands[0]
                if len(self._operands) == 1 and isinstance(self._operands[0], (list, tuple))
                else self._operands
            )
            evaluated = [o._get_value() if isinstance(o, Observable) else o for o in items]
            return op(evaluated)
        args = [o._get_value() if isinstance(o, Observable) else o for o in self._operands]
        return op(*args)

    def _get_value(self):
        return self._compute()

    # ------------------------------------------------------------------ leaf traversal
    def _collect_leaves(self) -> List['ObservableVariable']:
        if self._leaves is not None:
            return self._leaves
        seen: set = set()
        leaves: List[ObservableVariable] = []
        # seed the stack, handling any/all list operand
        stack: list = list(self._operands)
        if len(stack) == 1 and isinstance(stack[0], (list, tuple)):
            stack = list(stack[0])
        while stack:
            o = stack.pop()
            if isinstance(o, ObservableVariable):
                if id(o) not in seen:
                    seen.add(id(o))
                    leaves.append(o)
            elif isinstance(o, ObservableExpression):
                for leaf in o._collect_leaves():
                    if id(leaf) not in seen:
                        seen.add(id(leaf))
                        leaves.append(leaf)
            elif isinstance(o, (list, tuple)):
                stack.extend(o)
        self._leaves = leaves
        return leaves

    # ------------------------------------------------------------------ link / unlink
    def link(self, event):
        should_reset = event._should_reset_on_false

        def handler(change=None):
            if self._compute():
                event.trigger()
            elif should_reset:
                event.reset()

        leaves = self._collect_leaves()
        self._link_handlers[id(event)] = (handler, leaves)
        for leaf in leaves:
            leaf._store.observe('changed', handler)
        # Mirror reaktiv Effect: check current value immediately
        if self._compute():
            event.trigger()

    def unlink(self, event):
        entry = self._link_handlers.pop(id(event), None)
        if entry is not None:
            handler, leaves = entry
            for leaf in leaves:
                try:
                    leaf._store.unobserve('changed', handler)
                except Exception:
                    pass

    # ------------------------------------------------------------------ static helpers
    @staticmethod
    def any(*predicate: Observable) -> 'ObservableExpression':
        return ObservableExpression(any, *predicate)

    @staticmethod
    def all(*predicate: Observable) -> 'ObservableExpression':
        return ObservableExpression(all, *predicate)

    def __repr__(self):
        name = getattr(self._op, '__name__', repr(self._op))
        return f"ObsExpr({name})"

    def __hash__(self):
        return hash(id(self))


# ---------------------------------------------------------------------------
# ObservableCollection  (experimental — kept for backward-compat imports)
# ---------------------------------------------------------------------------

class ObservableCollection(ObservableExpression):
    """Filtered observable collection over a list of ObservableVariable items."""

    def __init__(self, initial: Optional[Iterable], filter_func=lambda x: True, env=None):
        if not isinstance(initial, Iterable):
            raise TypeError("Initial value must be an iterable.")
        self._elements = ObservableVariable(list(initial) if not isinstance(initial, list) else initial)
        self._filter_func = filter_func
        super().__init__(
            lambda: [i._get_value() for i in self._elements._get_value() if filter_func(i._get_value())],
            env=env,
        )

    def append(self, element):
        self._elements._store.val.append(element)
        self._elements._store.changed = True
        self._leaves = None   # invalidate expression leaf cache

    def __iter__(self):
        return iter(self._get_value())

    def __getitem__(self, key):
        return self._elements._get_value()[key]


# ---------------------------------------------------------------------------
# ObservableProxy  (experimental — kept for backward-compat imports)
# ---------------------------------------------------------------------------

class ObservableProxy(ObservableExpression):
    """Observe a specific attribute or index of an observable target."""

    def __init__(self, target: Observable, accessor=None, attr_name: str = None):
        self._target = target
        self._accessor = accessor
        self._attr_name = attr_name
        super().__init__(lambda: self._resolve(), target)

    def _resolve(self):
        val = self._target._get_value()
        if self._accessor is not None:
            val = val[self._accessor]
        if self._attr_name is not None:
            val = getattr(val, self._attr_name)
        return val

    def item(self, index):
        return ObservableProxy(self._target, accessor=index)

    def attr(self, name: str):
        return ObservableProxy(self, attr_name=name)


if __name__ == "__main__":
    from hsim.core.core.env import Environment
    from hsim.core.core.event import BaseEvent, ConditionedEvent
    from sortedcontainers import SortedList

    # Smoke test: variable → expression → event chain
    env = Environment()
    q = ObservableVariable(SortedList())
    q_len = q.length()
    cond = q_len > 0

    triggered = []
    event = ConditionedEvent(env, condition=cond,
                             action=lambda: triggered.append(env.now)).add()
    q.add(42)
    env.run(1)
    assert triggered, "event should have fired after q.add()"
    print("smoke test passed:", triggered)

