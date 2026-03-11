from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, Optional, Type, Union
from reaktiv import Signal, ComputeSignal, Effect
import operator
# Pre-import scipy to avoid import-time signature inspection issues before our patches
try:
    import scipy.stats
except ImportError:
    pass

# Monkey-patch Reaktiv's Signal.get() to avoid expensive f-string evaluation in debug_log
# The issue: debug_log(f"...{self._value}") evaluates the f-string even when debugging is disabled,
# causing __repr__() to be called on SortedList values (~125k times), consuming ~9 seconds
_original_signal_get = Signal.get

from reaktiv import graph
from reaktiv.signal import ComputeSignal
from reaktiv._debug import _debug_enabled
def _patched_signal_get(self):
    """Optimized Signal.get() that avoids f-string evaluation when debug logging is disabled."""
    # Bypassing lock check as thread-safety is disabled in this project context
    edge = graph.add_dependency(self)
    if edge is not None:
        edge.version = self._version
    if _debug_enabled:
        from reaktiv._debug import debug_log
        debug_log(f"Signal get() returning value: {self._value}")
    return self._value

Signal.get = _patched_signal_get

# Also patch Signal.set() which has the same debug_log issue
_original_signal_set = Signal.set

def _patched_signal_set(self, new_value):
    if _debug_enabled:
        from reaktiv._debug import debug_log
        debug_log(f"Signal set() called with new_value: {new_value} (old_value: {self._value})")

    # Simplified side-effect detection
    active = graph.active_consumer.get()
    if active is not None and isinstance(active, ComputeSignal):
        raise RuntimeError("Side effect detected: Cannot set Signal from within a ComputeSignal computation")

    # Bypassing lock as thread-safety is disabled
    self._set_internal(new_value)

Signal.set = _patched_signal_set

# Cache for inspect.signature results to avoid repeated expensive introspection
# This is safe because function signatures don't change during runtime
_signature_cache = {}
_original_inspect_signature = None

def _get_cached_signature(obj):
    """Get signature with caching by object id."""
    obj_id = id(obj)
    if obj_id not in _signature_cache:
        _signature_cache[obj_id] = _original_inspect_signature(obj)
    return _signature_cache[obj_id]

# Monkey-patch inspect.signature AFTER module initialization
# This avoids interfering with scipy's module-import-time signature introspection
_patch_applied = False
def _apply_signature_cache_patch():
    """Delay patch application until after scipy loads."""
    global _patch_applied, _original_inspect_signature
    if not _patch_applied:
        import inspect as _inspect_module
        _original_inspect_signature = _inspect_module.signature
        _inspect_module.signature = _get_cached_signature
        _patch_applied = True


class Observable(ABC):
    
    @property
    def value(self):
        """Backward compatibility - delegate to Reaktiv's call syntax"""
        return self._get_value()
    
    def _get_value(self):
        """Bypass Reaktiv graph evaluation if not in a reactive context."""
        # Only bypass for simple Signals, not ComputeSignals (Expressions)
        # which need to check for stale dependencies.
        if graph.active_consumer.get() is None and not isinstance(self, ComputeSignal):
            if hasattr(self, '_value'):
                return self._value
        return self()  # Fallback to reactive Signal.get() / ComputeSignal()

    def add_environment(self, env) -> None:
        self._env = env
        
    def link(self, event):
        _apply_signature_cache_patch()  # Apply patch at first runtime use, not import time
        self._event = event
        self._effect = Effect(lambda: event.trigger() if self() else event.reset())  # Dummy effect to trigger updates

    def unlink(self, event):
        self._effect.dispose()
    
    def __add__(self, other: Any):
        return ObservableExpression(operator.add, self, other)
    
    def __radd__(self, other: Any):
        return self + other
    
    def __iadd__(self, other: Any):
        self.set(self._value + other)
        return self
    
    def __sub__(self, other: Any):
        return ObservableExpression(operator.sub, self, other)
    
    def __rsub__(self, other: Any):
        return ObservableExpression(operator.sub, other, self)
    
    def __isub__(self, other: Any):
        self.set(self._value - other)
        return self
    
    def __mul__(self, other: Any):
        return ObservableExpression(operator.mul, self, other)
    
    def __rmul__(self, other: Any):
        return self * other
    
    def __imul__(self, other: Any):
        self.set(self._value * other)
        return self
    
    def __truediv__(self, other: Any):
        return ObservableExpression(operator.truediv, self, other)
    
    def __rtruediv__(self, other: Any):
        return ObservableExpression(operator.truediv, other, self)
    
    def __itruediv__(self, other: Any):
        self.set(self._value / other)
        return self
    
    def __floordiv__(self, other: Any):
        return ObservableExpression(operator.floordiv, self, other)
    
    def __rfloordiv__(self, other: Any):
        return ObservableExpression(operator.floordiv, other, self)
    
    def __mod__(self, other: Any):
        return ObservableExpression(operator.mod, self, other)
    
    def __rmod__(self, other: Any):
        return ObservableExpression(operator.mod, other, self)
    
    def __pow__(self, other: Any):
        return ObservableExpression(operator.pow, self, other)
    
    def __rpow__(self, other: Any):
        return ObservableExpression(operator.pow, other, self)
        
    def __eq__(self, other):
        return ObservableExpression(operator.eq, self, other)
        
    def __ne__(self, other: Any):
        return ObservableExpression(operator.ne, self, other)
    
    def __lt__(self, other: Any):
        return ObservableExpression(operator.lt, self, other)
    
    def __le__(self, other: Any):
        return ObservableExpression(operator.le, self, other)
    
    def __gt__(self, other: Any):
        return ObservableExpression(operator.gt, self, other)
    
    def __ge__(self, other: Any):
        return ObservableExpression(operator.ge, self, other)

    def __ishift__(self, other: Any):
        """Shift operator."""
        self.set(other)
        return self

    def __ilshift__(self, other: Any):
        return self.__ishift__(other)
    
    def __irshift__(self, other: Any):
        return self.__ishift__(other)
    
        # Boolean operators
    def __and__(self, other: Any):
        return ObservableExpression(operator.and_, self, other)
    
    def __rand__(self, other: Any):
        return ObservableExpression(operator.and_, other, self)
    
    def __or__(self, other: Any):
        return ObservableExpression(operator.or_, self, other)
    
    def __ror__(self, other: Any):
        return ObservableExpression(operator.or_, other, self)
    
    # Unary operators
    def __neg__(self):
        return ObservableExpression(operator.neg, self)
    
    def __pos__(self):
        return ObservableExpression(operator.pos, self)
    
    def __abs__(self):
        return ObservableExpression(operator.abs, self)
    
    def __bool__(self):
        """Return True if the observable's value is truthy, False otherwise."""
        return bool(self._get_value())
    
    def __len__(self):
        val = self._get_value()
        if val is None:
            return 0
        if not hasattr(val, "__len__"):
            # raise TypeError(f"object of type '{type(self.value).__name__}' has no len()")
            # print(f"Warning: object of type '{type(val).__name__}' has no len(), returning 0")
            return 0
        return len(val)

    @staticmethod
    def any(*predicate: 'Observable') -> 'ObservableExpression':
        """
        Returns an ObservableExpression that is True if any element of the value is true (or satisfies the predicate).
        """
        return ObservableExpression(any,*predicate)
    
    @staticmethod    
    def all(*predicate: 'Observable') -> 'ObservableExpression':
        """
        Returns an ObservableExpression that is True if all elements of the value are true (or satisfy the predicate).
        """
        return ObservableExpression(all, *predicate)

    def __hash__(self):
        return hash(id(self))
    
    def __getitem__(self, key):
        return self._get_value()[key]
    
    def proxy(self, accessor: Any = None, attr_name: str = None) -> 'ObservableProxy':
        """
        Create an ObservableProxy to observe a specific part of this observable.
        
        Args:
            accessor: Index or key for collection access  
            attr_name: Attribute name for property access
        """
        return ObservableProxy(self, accessor=accessor, attr_name=attr_name)
    

class ObservableExpression(ComputeSignal, Observable):
    def __init__(self, op: Callable, *operands: Union['ObservableVariable','ObservableExpression'],env=None):
        if getattr(op, "__name__", "") in ["all", "any"] or op in [all, any]:
            # For all/any, the first operand is usually a list of elements
            # Let's write an optimized evaluation that avoids isinstance inside the lambda
            items = operands[0]
            if isinstance(items, (list, tuple)):
                is_obs = [isinstance(item, (ObservableVariable, ObservableExpression)) for item in items]
                
                def _eval_all_any():
                    res = []
                    for i, item in enumerate(items):
                        res.append(item() if is_obs[i] else item)
                    return op(res)
                
                super().__init__(_eval_all_any)
            else:
                super().__init__(lambda: op([operand() if isinstance(operand, (ObservableVariable, ObservableExpression)) else operand for operand in operands[0]]))
        elif len(operands) == 0:
            super().__init__(op)
        else:
            is_obs = [isinstance(operand, (ObservableVariable, ObservableExpression)) for operand in operands]
            
            def _eval_op():
                res = []
                for i, operand in enumerate(operands):
                    res.append(operand() if is_obs[i] else operand)
                return op(*res)
                
            super().__init__(_eval_op)
        self.op = op
        self.operands = operands
        self.env = env

    # @property
    # def value(self):
    #     """Backward compatibility - delegate to Reaktiv's call syntax"""
    #     return self()  # ComputeSignal.__call__ returns cached value

class ObservableVariable(Signal, Observable):
    def __init__(self, initial: Any, env=None):
        super().__init__(initial)
        self._env = env         
        if isinstance(initial, Iterable):
            self._equal = lambda x, y : False 
        
    @property
    def value(self):
        """Backward compatibility - delegate to Reaktiv's call syntax"""
        return self._get_value()

    @value.setter
    def value(self, new_value):
        """Backward compatibility - delegate to Signal.set()"""
        self.set(new_value)
            
    def __repr__(self):
        return f"{self._value} (Obs: {id(self)})"
    
    def __str__(self):
        return f"{self._value} (Obs)"
    
    def __hash__(self):
        return hash(id(self))
    
    # Mathematical operators that return ObservableExpression
    
    @staticmethod
    def any(*predicate: 'ObservableVariable') -> 'ObservableExpression':
        """
        Returns an ObservableExpression that is True if any element of the value is true (or satisfies the predicate).
        """
        return ObservableExpression(any,*predicate)
    
    @staticmethod    
    def all(*predicate: 'ObservableVariable') -> 'ObservableExpression':
        """
        Returns an ObservableExpression that is True if all elements of the value are true (or satisfy the predicate).
        """
        return ObservableExpression(all, *predicate)
    
    def length(self):
        """Return an ObservableExpression representing the length of the collection."""
        return ObservableExpression(len, self)
    
    def __iter__(self):
        """Iterate over the filtered collection."""
        return iter(self.value)
    
    def append(self, element):
        """Append an element to the collection."""
        self.update(lambda x:x.append(element) or x)
        # self.set(self._value + [element])

    def add(self, other: Any):
        self.update(lambda x: x.add(other) or x)
        
    def pop(self, index=-1):
        popped = self._value.pop(index)
        self.set(self._value)
        return popped
    
    def remove(self, element):
        self.update(lambda x: x.remove(element) or x)
        
    def extend(self, iterable):
        self.set(self._value + iterable)
    
    def clear(self):
        if isinstance(self._value, Iterable):
            self.set(type(self._value)())
        else:
            self.set(None)


class ObservableCollection(ObservableExpression):
    def __init__(self, initial: Optional[Iterable], filter_func = lambda x: True, env=None):
        self._elements = ObservableVariable(initial)
        if not isinstance(initial, Iterable):
            raise TypeError("Initial value must be an iterable.")
        super().__init__(lambda: type(initial)(i() for i in self._elements() if filter_func(i())), env=env)
        
    def append(self, element):
        """Append an element to the collection."""
        self._elements.set(self._elements() + [element])

    
    def insert(self, index, element):
        """Insert an element at the specified index."""
        self.set(self().insert(index, element))


    def pop(self, index=-1):
        """Remove and return element at index (default last)."""
        try:
            self.set(self().pop(index))
        except IndexError:
            raise IndexError("pop index out of range")
    
    def remove(self, element):
        """Remove first occurrence of element."""
        try:
            self.set(self().remove(element))
        except ValueError:
            raise ValueError("element not in collection")
    
    def clear(self):
        """Remove all elements from the collection."""
        self.set([])
    
    def extend(self, iterable):
        """Extend collection with elements from iterable."""
        self.set(self() + list(iterable))

    def length(self):
        """Return an ObservableExpression representing the length of the collection."""
        return ObservableExpression(len, self)
    
    def __iter__(self):
        """Iterate over the filtered collection."""
        return iter(self.value)
    
    def __getitem__(self, key):
        return self._elements[key]
    
    # def any(self):
    #     """Return an ObservableExpression that is True if any element in the collection is truthy."""
    #     return ObservableExpression(any, self)
    
    # def all(self):
    #     """Return an ObservableExpression that is True if all elements in the collection are truthy."""
    #     return ObservableExpression(all, self)
    
class ObservableProxy(ObservableExpression):
    """
    Use case 1: I get an element out of a collection, e.g., collection[0], and I want to observe changes to that element (i.e., if the element at position 0 changes, I want to be notified).
    Use case 2: I want to observe a specific property of a watchable object, such that if the object changes, I am notified.
    """
    
    def __init__(self, target: Union[ObservableVariable, ObservableExpression, ObservableCollection], accessor: lambda x: x, filter_func = lambda x: True):
        """
        Create a proxy that observes a specific part of an observable object.
        
        Args:
            target: The observable object to proxy
            accessor: Index or key for collection access (use case 1)  
            attr_name: Attribute name for property access (use case 2)
        """
        self.target = target
        

if __name__ == "__main__":
    if False:
        a = ObservableVariable(1)
        b = ObservableVariable(2)
        fil = lambda x: x % 2 == 1
        c = ObservableCollection([a,b], fil)
        e = Effect(lambda: print(c()))
        c.append(ObservableVariable(3))
    if False:
        k = ObservableCollection([])
        f = k.length()>0
        e2 = Effect(lambda: print("Length > 0:", f()))
        k.append(ObservableVariable(10))
    if True:
        a = ObservableVariable([10,20,30])
        b = ObservableExpression(lambda: len(a()))
        e3 = Effect(lambda: print("Length of a:", b()))
        a.append(40)
        a.pop()
        a.remove(10)
        a.extend([50,60])
        a.clear()
    if False:
        import time
        N = 1000
        t0 = time.time()
        for _ in range(N):
            a.append(10)
        print(f"Time for {N} appends:", time.time()-t0)
        t0 = time.time()
        for _ in range(N):
            a.pop()
        print(f"Time for {N} pops:", time.time()-t0)
        t0 = time.time()
        l = list()
        for _ in range(N):
            l.append(10)
        print(f"Time for {N} appends:", time.time()-t0)
        t0 = time.time()
        for _ in range(N):
            l.pop()
        print(f"Time for {N} pops:", time.time()-t0)

            
