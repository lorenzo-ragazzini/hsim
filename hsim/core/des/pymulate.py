from warnings import warn
from typing import Callable, Union, Optional, List, Dict
import numpy as np
import types
import random
if __name__ == "__main__":
    import sys
    import os
    try:
        sys.path.append("/".join(os.path.abspath(__file__).split("/")[:os.path.abspath(__file__).split("/").index("hsim")+1]))
    except:
        sys.path.append("//".join(os.path.abspath(__file__).split("\\")[:os.path.abspath(__file__).split("\\").index("hsim")+1]))
from hsim.core.agent.q import Queue
from hsim.core.fsm.transitions import MessageTransition, TimeoutTransition, EventTransition
from hsim.core.fsm.states import State
from hsim.core.fsm.FSM import FSM
from hsim.core.core.env import Environment
from hsim.core.agent.agent import Agent, FSM
from hsim.core.des.des import DESBlock, TimedBlock


def forwardItemB2S(self,item):
    try:
        _, msg = self.exit(item)
        msg.receipts["received"].action = self.transitionsFrom["Blocking"][0]
    except AttributeError as e:
        warn(RuntimeWarning(e))


class Server(DESBlock, TimedBlock):
    def __init__(self,env,name=None,serviceTime=1,serviceTimeFunction=None) -> None:
        super().__init__(env,name)
        self.var.serviceTime = serviceTime
        self.var.serviceTimeFunction = serviceTimeFunction
    def on_receive(self) -> None:
        self.stateMachine.transitionsFrom["Starving"][0]()
    class FSM(FSM):
        class Starving(State):
            initial_state=True
        class Working(State):
            def on_enter(self):
                self.var.item, self.var.message = self.store.inspect()
                self.transitions[0].timeout = self.calculateServiceTime(self.var.item)
        class Blocking(State):
            pass

        S2W=MessageTransition.define(Starving, Working)
        W2B=TimeoutTransition.define(Working, Blocking)
        B2S=EventTransition.define(Blocking, Starving)

        W2B.on_transition = lambda self: forwardItemB2S(self,self.var.item)
        B2S.on_transition = lambda self: self._fsm._agent.store.get() if self._fsm._agent.store else None
        

class Buffer(DESBlock):
    """
    Pushes first agent according to dispatching rule.
    """
    def __init__(self,env,name=None,capacity=np.inf):
        super().__init__(env,name,capacity)
    def on_receive(self):
        self.stateMachine.transitionsFrom["Starving"][0]()

    class FSM(FSM):
        class Starving(State):
            initial_state=True
        class Blocking(State):
            pass
        T1=MessageTransition.define(Starving, Blocking)
        T2=EventTransition.define(Blocking, Starving)

        T1.on_transition = lambda self: forwardItemB2S(self,self.store.inspect(index = -1)[0])
        T2.on_transition = lambda self: self._fsm._agent.store.get()


class Store(DESBlock):
    """
    Pushes every agent.
    
    Note: does not require a FSM.
    """
    def __init__(self,env,name=None,capacity=np.inf):
        super().__init__(env,name,capacity=capacity)
    def on_receive(self):
        self._forward_item()

    def _forward_item(self):
        item, _ = self.store.inspect(index = -1) # get the last item
        _, msg = self.exit(item)
        msg.receipts["received"].action = self.store.pull
        msg.receipts["received"].arguments = (item,)
        
def forwardItemEmpty(self):
    item, oldMsg = self.store.inspect(index = -1)
    _, msg = self.exit(item)
    if oldMsg.receipts["received"].action is None:
        msg.receipts["received"].action = self.transitionsFrom["Blocking"][0]
    elif isinstance(oldMsg.receipts["received"].action,list):
        msg.receipts["received"].action = oldMsg.receipts["received"].action + [self.transitionsFrom["Blocking"][0] ]
    else:
        msg.receipts["received"].action = [oldMsg.receipts["received"].action, self.transitionsFrom["Blocking"][0]]


class EmptyBuffer(DESBlock):
    _alwaysEmpty = True
    def __init__(self,env,name=None,capacity=np.inf):
        super().__init__(env,name,capacity,queueType="locked")
    def on_receive(self):
        self.stateMachine.transitionsFrom["Starving"][0]()
    
    class FSM(FSM):
        class Starving(State):
            initial_state=True
        class Blocking(State):
            pass
        T1=MessageTransition.define(Starving, Blocking)
        T2=EventTransition.define(Blocking, Starving)
                
        T1.on_transition = lambda self: forwardItemEmpty(self)
        T2.on_transition = lambda self: self._fsm._agent.store.get()

    


class Generator(DESBlock, TimedBlock):
    """Generates agents.
    Args:
        agent_function: Callable[[],Agent] - function that generates agents.
        moments: List[float] - exact scheduled arrival times (absolute)
        equidistant: bool - if True, spread N arrivals evenly in [at, till]
        at: float - start time for equidistant mode
        till: float - end time for equidistant mode
        at_end: Callable - callback invoked when generation wave ends
        disturbance: {callable, float, Distribution} - jitter on inter-arrival times
    """
    def __init__(self, env, name=None,
                 agent_function:Union[Callable[[],Agent],Agent]=Agent,
                 serviceTime=0,
                 serviceTimeFunction=None,
                 # generation configuration
                 generation_mode: str = "",
                 batch_size: int = 1,
                 production_plan: Optional[List[Dict]] = None,
                 production_mix: Optional[Union[Dict[Callable, float], List[tuple]]] = None,
                 plan_release_time: bool = False,
                 # new generation features
                 moments: Optional[List[float]] = None,
                 equidistant: bool = False,
                 at: float = 0.0,
                 till: float = 100.0,
                 at_end: Optional[Callable] = None,
                 disturbance: Union[None, float, Callable] = None,
                 ):
        super().__init__(env, name)
        self._counter = 0
        if not callable(agent_function):
            raise ValueError("Agent function must be a callable or an Agent class")
        elif isinstance(agent_function,type):
            self.agent_function = types.MethodType(lambda self: Agent(self.env), self)
        else:
            self.agent_function = types.MethodType(agent_function, self) 
        self.var.serviceTime = serviceTime
        self.var.serviceTimeFunction = serviceTimeFunction
        # generation configuration
        self.generation_mode = generation_mode
        self.batch_size = int(batch_size) if batch_size and batch_size > 0 else 1
        self.production_plan = production_plan
        self.production_mix = production_mix
        # if True, times in production_plan are release times (absolute) instead of interarrival
        self.plan_release_time = bool(plan_release_time)
        
        # new generation features
        self.moments = list(moments) if moments else None
        self.equidistant = bool(equidistant)
        self.at = float(at)
        self.till = float(till)
        self.at_end = at_end  # callback when generation ends
        self.disturbance = disturbance  # jitter function/value/distribution
        
        # internal state for moments and equidistant generation
        self._moments_index = 0
        self._equidistant_arrivals = []
        
        # pre-compute equidistant arrivals if enabled
        if self.equidistant:
            self._compute_equidistant_arrivals()

        # allow passing pandas DataFrame for production_plan or production_mix
        try:
            import pandas as pd
        except Exception:
            pd = None

        if pd is not None and isinstance(self.production_plan, pd.DataFrame):
            # convert dataframe rows to dict records
            try:
                self.production_plan = self.production_plan.to_dict("records")
            except Exception as e:
                raise AssertionError(f"production_plan DataFrame conversion failed: {e}")

        if pd is not None and isinstance(self.production_mix, pd.DataFrame):
            # expect columns: 'agent' and 'weight' (or 'prob')
            cols = [c.lower() for c in self.production_mix.columns]
            if "agent" in cols and ("weight" in cols or "prob" in cols):
                agent_col = self.production_mix.columns[cols.index("agent")]
                weight_col = self.production_mix.columns[cols.index("weight")] if "weight" in cols else self.production_mix.columns[cols.index("prob")]
                try:
                    self.production_mix = [(row[agent_col], float(row[weight_col])) for _, row in self.production_mix.iterrows()]
                except Exception as e:
                    raise AssertionError(f"production_mix DataFrame conversion failed: {e}")
            else:
                raise AssertionError("production_mix DataFrame must have columns 'agent' and 'weight' (or 'prob')")

        # validate coherence between declared generation_mode and provided plan/mix
        self._validate_generation_config()

        # internal plan cursor
        self._plan_index = 0
        self._plan_time_cursor = 0.0

        # ensure production_mix normalized if provided as dict
        if isinstance(self.production_mix, dict):
            self._mix_items = list(self.production_mix.items())
        elif isinstance(self.production_mix, list):
            self._mix_items = list(self.production_mix)
        else:
            self._mix_items = None

        # initial timeout
        self.stateMachine.transitionsFrom["Starving"][0].timeout = self.calculateServiceTime()
    
    def _compute_equidistant_arrivals(self):
        """Pre-compute arrival times evenly spaced in [at, till].
        
        Generates batch_size arrival times distributed evenly across the interval.
        """
        if self.batch_size <= 0:
            return
        
        if self.batch_size == 1:
            # Single arrival at start
            self._equidistant_arrivals = [self.at]
        else:
            # N arrivals: spread across [at, till] with N-1 equal intervals
            interval = (self.till - self.at) / (self.batch_size - 1)
            self._equidistant_arrivals = [self.at + i * interval for i in range(self.batch_size)]
    
    def _apply_disturbance(self, iat: float) -> float:
        """Apply jitter to inter-arrival time based on disturbance setting."""
        if self.disturbance is None:
            return iat
        
        # callable: assume it returns a scalar
        if callable(self.disturbance):
            jitter = self.disturbance()
        # numeric: assume it's a std dev or absolute value
        elif isinstance(self.disturbance, (int, float)):
            jitter = random.gauss(0, self.disturbance)  # normal distribution around 0
        else:
            jitter = 0.0
        
        return max(0.0, iat + jitter)  # prevent negative IAT
    class FSM(FSM):
        class Starving(State):
            initial_state=True
        class Blocking(State):
            pass
        T1=TimeoutTransition.define(Starving, Blocking)
        T2=EventTransition.define(Blocking, Starving)

        
        # on generate, delegate to the parent Generator instance for more advanced behaviour
        T1.on_transition = lambda self: self._fsm._agent._on_generate(self)
        T2.on_transition = lambda self: None


    def _validate_generation_config(self):
        """Validate `generation_mode`, `production_plan`, and `production_mix` formats and coherence."""
        allowed_modes = {"", "plan", "mix", "single", "batch"}
        if self.generation_mode not in allowed_modes:
            raise AssertionError(f"Unsupported generation_mode '{self.generation_mode}'")

        if self.generation_mode == "plan":
            assert self.production_plan is not None, "generation_mode 'plan' requires a production_plan"
            assert isinstance(self.production_plan, list), "production_plan must be a list of dicts or a DataFrame"
            for entry in self.production_plan:
                assert isinstance(entry, dict), "each production_plan entry must be a dict"
                # If plan_release_time is True, entries may omit 'time' and are treated as immediate
                if not self.plan_release_time:
                    if not any(k in entry for k in ("time", "release_time", "intergen", "interarrival")):
                        raise AssertionError("production_plan entries must include 'time'/'release_time' or 'intergen'/'interarrival'")

        if self.generation_mode == "mix":
            assert self.production_mix is not None, "generation_mode 'mix' requires a production_mix"
            if isinstance(self.production_mix, dict):
                for k, v in self.production_mix.items():
                    assert isinstance(v, (int, float)), "production_mix dict values must be numeric weights"
            elif isinstance(self.production_mix, list):
                for item in self.production_mix:
                    assert isinstance(item, (tuple, list)) and len(item) >= 2, "production_mix list entries must be (agent, weight)"
                    assert isinstance(item[1], (int, float)), "weights in production_mix must be numeric"
            else:
                raise AssertionError("production_mix must be a dict or list of (agent, weight)")

        if self.generation_mode == "":
            assert self.production_plan is None and self.production_mix is None, "Empty generation_mode requires no production_plan nor production_mix"


    def _choose_from_mix(self):
        """Choose an agent function from the production mix based on weights."""
        if not self._mix_items:
            return self.agent_function
        # _mix_items is list of (callable, weight)
        funcs, weights = zip(*self._mix_items)
        total = sum(weights)
        if total <= 0:
            probs = [1.0 / len(weights)] * len(weights)
        else:
            probs = [w / total for w in weights]
        choice = random.choices(funcs, probs, k=1)[0]
        if isinstance(choice, type):
            return types.MethodType(lambda self, c=choice: c(self.env), self)
        elif callable(choice):
            return types.MethodType(choice, self)
        else:
            return self.agent_function

    def calculateServiceTime(self, entity:Optional[Agent]=None, attribute: str = 'serviceTime') -> Optional[float]:
        """Wrapper for service time calculation.

        - If `moments` is present, compute interval to next scheduled moment (absolute time)
        - If `equidistant` is True, compute interval to next equidistant arrival
        - If a `production_plan` is present, compute the next interval from the current plan
          entry (without creating agents).
        - Otherwise defer to the original TimedBlock calculation.
        """
        # moments: exact scheduled arrival times (absolute)
        if self.moments:
            if self._moments_index >= len(self.moments):
                return None
            next_time = self.moments[self._moments_index]
            interval = max(0.0, next_time - self.env.now)
            return interval
        
        # equidistant: arrivals spread evenly in [at, till]
        if self.equidistant and self._equidistant_arrivals:
            if self._moments_index >= len(self._equidistant_arrivals):
                return None
            next_time = self._equidistant_arrivals[self._moments_index]
            interval = max(0.0, next_time - self.env.now)
            return interval
        
        # If there's a plan, compute from plan entry (do not create agents here)
        if self.production_plan:
            if self._plan_index >= len(self.production_plan):
                return None
            entry = self.production_plan[self._plan_index]
            if self.plan_release_time:
                # release_time may be missing; treat missing release_time as immediate (0.0)
                release_time = None
                if isinstance(entry, dict):
                    # prefer explicit 'time', then 'release_time'
                    if "time" in entry:
                        release_time = entry.get("time")
                    elif "release_time" in entry:
                        release_time = entry.get("release_time")
                if release_time is None:
                    # release immediately
                    return 0.0
                interval = float(release_time) - float(self.env.now)
                return max(0.0, interval)
            else:
                inter = entry.get("intergen") or entry.get("interarrival")
                if inter is None:
                    from hsim.core.des.des import TimedBlock as _TimedBlock
                    return _TimedBlock.calculateServiceTime(self, entity, attribute)
                # apply disturbance to IAT
                iat = float(inter)
                return self._apply_disturbance(iat)

        # No production plan: delegate to original TimedBlock implementation
        from hsim.core.des.des import TimedBlock as _TimedBlock
        iat = _TimedBlock.calculateServiceTime(self, entity, attribute)
        if iat is not None:
            iat = self._apply_disturbance(iat)
        return iat

    def _create_agents_for_entry(self, entry=None):
        """Create list of agents for a plan entry or according to mode."""
        agents = []
        if entry:
            count = int(entry.get("count", 1))
            agent_spec = entry.get("agent", None)
            if agent_spec is None:
                # fallback to default agent function
                for _ in range(count):
                    agents.append(self.agent_function())
            else:
                for _ in range(count):
                    if isinstance(agent_spec, type):
                        agents.append(agent_spec(self.env))
                    elif callable(agent_spec):
                        # bind to self if required
                        try:
                            bound = types.MethodType(agent_spec, self)
                            agents.append(bound())
                        except Exception:
                            agents.append(agent_spec())
                    else:
                        agents.append(self.agent_function())
            # map any extra attributes from the plan entry onto created agents
            # skip generation-control keys
            skip_keys = {"agent", "count", "time", "release_time", "intergen", "interarrival"}
            for agent in agents:
                if isinstance(entry, dict):
                    for k, v in entry.items():
                        if k in skip_keys:
                            continue
                        # treat 'route' specially: ensure it's a list on the agent
                        if k == "route":
                            try:
                                setattr(agent, "route", list(v) if v is not None else [])
                                # initialize route cursor if not present
                                if not hasattr(agent, "route_index"):
                                    setattr(agent, "route_index", 0)
                            except Exception:
                                setattr(agent, "route", v)
                        else:
                            try:
                                setattr(agent, k, v)
                            except Exception:
                                pass
            return agents

        # no entry -> use modes
        if self.generation_mode == "plan":
            return []
        if self.generation_mode == "mix":
            # pick batch_size elements from mix
            for _ in range(self.batch_size):
                f = self._choose_from_mix()
                try:
                    agents.append(f())
                except Exception:
                    # fallback
                    agents.append(self.agent_function())
            return agents
        # default or single/batch
        for _ in range(self.batch_size):
            agents.append(self.agent_function())
        return agents

    def _on_generate(self, fsm_state):
        """Called when the generator's timeout transition triggers."""
        # If we have a production plan, use current plan entry
        entry = None
        if self.production_plan:
            if self._plan_index >= len(self.production_plan):
                return None
            entry = self.production_plan[self._plan_index]

        agents = self._create_agents_for_entry(entry)

        # forward each created agent to the next block using existing helper
        for item in agents:
            try:
                forwardItemB2S(fsm_state, item)
            except Exception as e:
                warn(RuntimeWarning(e))

        # advance cursor based on generation mode
        if self.production_plan:
            self._plan_index += 1
        elif self.moments or self.equidistant:
            self._moments_index += 1

        # schedule next interval; do not assign a None timeout (prevents scheduler errors)
        next_interval = self.calculateServiceTime()
        if next_interval is not None:
            try:
                fsm_state.transitions[0].timeout = next_interval
            except Exception:
                pass
        else:
            # no further scheduling: generation wave complete
            # invoke at_end callback if provided
            if self.at_end is not None:
                try:
                    if callable(self.at_end):
                        self.at_end()
                except Exception as e:
                    warn(RuntimeWarning(f"at_end callback failed: {e}"))
            
            # try to deactivate the generator FSM to avoid further transitions
            try:
                if hasattr(self, "deactivate_fsm"):
                    try:
                        self.deactivate_fsm()
                    except Exception:
                        pass
            except Exception:
                pass


class Terminator(DESBlock):
    """
    Terminates agent.
    
    Note: does not require a FSM.
    """
    def __init__(self,env,name=None):
        super().__init__(env,name,capacity=np.inf)
    def on_receive(self):
        self._terminate_item()

    def _terminate_item(self):
        item, msg = self.store.inspect(index = -1) # get the last item
        item.deactivate_fsm()
        
def example_agent_function(obj):
    return Agent(obj.env)

def test1():
    env = Environment()
    a = Server(env)
    q = Queue(env,10)
    a.connections["next"] = q
    env.run(10)
    x = Agent(env,"test")
    a.take(x)
    env.run(20)
    a.take(Agent(env,"test"))
    env.run(30)
    
def test2():
    env = Environment()
    a = Server(env)
    b = Buffer(env)
    q = Queue(env,10)
    a.connections["next"] = b
    b.connections["next"] = q
    env.run(10)
    x1 = Agent(env,"test1")
    a.take(x1)
    env.run(20)
    x2 = Agent(env,"test2")
    a.take(x2)
    env.run(30)
    
def test3():
    env = Environment()
    a = Server(env)
    b = Store(env)
    q = Queue(env,10)
    a.connections["next"] = b
    b.connections["next"] = q
    env.run(10)
    x1 = Agent(env,"test1")
    a.take(x1)
    env.run(20)
    x2 = Agent(env,"test2")
    a.take(x2)
    env.run(30)
    
def test4():
    env = Environment()
    g = Generator(env,"",example_agent_function,serviceTime=10)
    t = Terminator(env)
    g.connections["next"] = t
    env.run(100)
    
    
def test5():
    env = Environment()
    g = Generator(env,"",Agent,serviceTime=10)
    t = Terminator(env)
    g.connections["next"] = t
    env.run(100)

def test5():
    env = Environment()
    g = Generator(env,"",Agent,serviceTime=10)
    q1 = Buffer(env,capacity=2)
    q2 = Buffer(env,capacity=2)
    t = Terminator(env)
    g.connections["next"] = q1
    q1.connections["next"] = q2
    q2.connections["next"] = t
    env.run(100)
    
def test5():
    env = Environment()
    g = Generator(env,"",Agent,serviceTime=10)
    s1 = Server(env,serviceTime=10)
    s2 = Server(env,serviceTime=10)
    t = Terminator(env)
    g.connections["next"] = s1
    s1.connections["next"] = s2
    s2.connections["next"] = t
    env.run(100)
    pass
    
def test6():
    env = Environment()
    g = Generator(env,"",Agent,serviceTime=10)
    b0 = EmptyBuffer(env,capacity=1)
    b1 = Buffer(env,capacity=2)
    s = Server(env,serviceTime=10)
    t = Terminator(env)
    g.connections["next"] = b0
    b0.connections["next"] = b1
    b1.connections["next"] = s
    s.connections["next"] = t
    env.run(100)
    
def test7():
    env = Environment()
    g = Generator(env,"",Agent,serviceTime=1)
    b = Buffer(env,capacity=2)
    s = Server(env,serviceTime=10)
    t = Terminator(env)
    g.connections["next"] = b
    b.connections["next"] = s
    s.connections["next"] = t
    env.run(100)
    
def test8():
    import pandas as pd
    import pstats
    import cProfile
    def run_test():
        env = Environment()
        g = Generator(env,"",Agent,serviceTime=10)
        s1 = Server(env,serviceTime=10)
        s2 = Server(env,serviceTime=10)
        t = Terminator(env)
        g.connections["next"] = s1
        s1.connections["next"] = s2
        s2.connections["next"] = t
        env.run(50000)
        pass
    profiler = cProfile.Profile()
    try:
        profiler.runcall(run_test)
    except Exception as e:
        print(f"Error: {e}")
    profiler.dump_stats("output.prof")

    stats = pstats.Stats(profiler)
    stats.sort_stats("cumtime")
    data = [
        {
            "Function": f"{func[0]}:{func[1]}({func[2]})",
            "Calls": cc,
            "Total Time": tt,
            "Cumulative Time": ct,
            "Per Call (Total)": tt / nc if nc else 0,
            "Per Call (Cumulative)": ct / nc if nc else 0
        }
        for func, (cc, nc, tt, ct, callers) in stats.stats.items()
    ]
    df = pd.DataFrame(data).to_excel("profiler_stats.xlsx", index=False)
    
if __name__ == "__main__":
    test1()
    test2()
    test3()
    test4()
    test5()
    test6()
    test7()
    # test8()
    print("Tests completed.")