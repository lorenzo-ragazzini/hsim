if __name__ == "__main__":
    import sys
    import os
    try:
        sys.path.append("/".join(os.path.abspath(__file__).split("/")[:os.path.abspath(__file__).split("/").index("hsim")+1]))
    except:
        sys.path.append("//".join(os.path.abspath(__file__).split("\\")[:os.path.abspath(__file__).split("\\").index("hsim")+1]))


from typing import Any, Dict, Iterable, List, Type, Union
import pandas as pd

from hsim.core.core.msg import Message, MessageQueue
from hsim.core.core.obs import ObservableExpression, ObservableVariable

class FSM:
    def __init__(self, env):
        self._env = env
        env._objects.append(self)
        self._states:List['State'] = []
        self._transitions:List['Transition'] = []
        self._transitions_dict:Dict[str, 'Transition'] = {}
        self._messages:MessageQueue = MessageQueue(env)
        self._pseudostates:List['Pseudostate'] = []
        self._state_history = []  # Track state history with timestamps
        self._transition_history = []  # Track transitions with timestamps
        self.add_element(get_class_dict(self, State))
        self.add_element(get_class_dict(self, Pseudostate))
        self.add_element(get_class_dict(self, Transition))
        self.active, self.startable, self.stoppable = False, True, True
        self._current_state = ObservableVariable(list())
    def start(self):
        for state in self._states:
            state.start() if state.initial_state else None
        self.active = True
    def stop(self):
        for state in self._states:
            state.stop()
        self.active = False
    def add_element(self, element: Union["State", "Transition", "Pseudostate", Type, Iterable]):
        if isinstance(element, Iterable):
            for e in element:
                self.add_element(e)
        elif not isinstance(element, type):
            if isinstance(element, State):
                self._states.append(element)
            elif isinstance(element, Transition):
                element._global_id = len(self._transitions)
                name = self._generate_transition_name(element.source, element.target)
                element.name = name
                self._transitions.append(element)
                self._transitions_dict[name] = element
                element.source._transitions_list.append(element)
                element.source._transitions_dict[name] = element
            elif isinstance(element, Pseudostate):
                self._pseudostates.append(element)
        elif isinstance(element, type):
            if issubclass(element, State):
                initial_state = getattr(element, 'initial_state', False)
                self.add_element(element(element.__name__, self, initial_state))
            elif issubclass(element, Transition):
                source, target = self.statesps[element._sourceStateClass.__name__], self.statesps[element._targetStateClass.__name__]
                new_transition = element(self, source, target).__override__()
                self.add_element(new_transition)
            elif issubclass(element, Pseudostate):
                self.add_element(element(element.__name__, self))
                
    def _generate_transition_name(self, source, target):
        base = f"{source.name[0].upper()}2{target.name[0].upper()}"
        name = base
        count = 2
        while name in self._transitions:
            name = f"{base}{count}"
            count += 1
        return name

    def receive(self, message):
        self._messages.receive(message)
        self._on_receive(message)
    def receiveContent(self, content, sender=None) -> Message:
        msg:Message = Message(self._env, content, sender=sender, receiver=self, wait=True)
        self.receive(msg)
        return msg
    def guard_message(self):
        msg = self._messages.get()
        matches = []
        # Only check transitions from the current active states
        for state in self._current_state.value:
            for transition in state._transitions_list:
                if isinstance(transition, MessageTransition) and transition.interpret(msg):
                    matches.append(transition)
        if matches:
            if len(matches) > 1:
                matches.sort(key=lambda x: x._global_id)
            for transition in matches:
                transition.event.trigger()
    def _on_receive(self, message):
        self.guard_message()
    @property
    def state_list(self):
        return self._states
    @property
    def transitions(self):
        return self._transitions
    @property
    def current_state(self):
        return self._current_state
    @property
    def states(self):
        return {state.name: state for state in self._states}
    @property
    def transitionsFrom(self):
        res = {name: [] for name in self.states}
        for transition in self._transitions:
            res[transition.source.name].append(transition)
        return res
    @property
    def transitionsTo(self):
        res = {name: [] for name in self.states}
        for transition in self._transitions:
            res[transition.target.name].append(transition)
        return res
    @property
    def transitionsFromTo(self):
        res = {}
        for transition in self._transitions:
            key = (transition.source, transition.target)
            if key not in res:
                res[key] = []
            res[key].append(transition)
        return res
    @property
    def pseudostates(self):
        return {state.name: state for state in self._pseudostates}
    @property
    def statesps(self):
        d = {state.name: state for state in self._states}
        d.update({state.name: state for state in self._pseudostates})
        return d
    def __getattr__(self, name: str) -> Any:
        # __getattr__ is only called when normal attribute lookup fails.
        # Optimize by avoiding redundant object.__getattribute__ call which always fails.
        if name == '_agent' or name.startswith('__'):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        try:
            return getattr(object.__getattribute__(self, '_agent'), name)
        except AttributeError as e:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'") from e

    def log_state_entry(self, state):
        self._state_history.append((state.name, True, self._env.now))
        cur = self._current_state.value
        if state not in cur:
            self._current_state.set(cur + [state])
            
    def log_state_exit(self, state):
        self._state_history.append((state.name, False, self._env.now))
        cur = self._current_state.value
        if state in cur:
            new_cur = [s for s in cur if s is not state]
            self._current_state.set(new_cur)
    def log_transition(self, source, target):
        self._transition_history.append((source.name, target.name, self._env.now))

    @property
    def state_history(self):
        return self._state_history
    @property
    def transition_history(self):
        return self._transition_history
    @property
    def state_history_table(self):
        return pd.DataFrame(self.state_history,columns=["State","I/O","Time"])
    @property
    def transition_history_table(self):
        return pd.DataFrame(self.transition_history,columns=["Source","Target","Time"])

def get_class_dict(par, sub):
    cls = [cls for cls in par.__class__.__mro__][0]
    z = {**cls.__dict__, **dict()}
    return [x for x in z.values() if hasattr(x,'__base__') and (x.__base__ is sub or (hasattr(x.__base__,'__base__') and x.__base__.__base__ is sub)) and type(x) is type]
        


from .transitions import Transition, MessageTransition
from .states import State, Pseudostate