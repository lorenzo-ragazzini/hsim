from hsim.core.core.env import HSimEnvironment
from hsim.core.core.event import DelayEvent
env = HSimEnvironment()
fired = []
DelayEvent(env, delay=5, action=lambda: fired.append(env.now)).add()
env.run(until=10)
assert fired == [5.0], f'Expected [5.0] got {fired}'
print('Step 6 OK — DelayEvent fired at t=5')
