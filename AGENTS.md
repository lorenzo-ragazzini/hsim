# AGENTS.md - Development Guidelines for hsim

This file provides guidance for AI agents working on the hsim codebase.

## Project Overview

hsim is a discrete event simulation (DES) framework for manufacturing system modeling, with a focus on the GSOM (Global Supply Operations Management) simulation game. It's a Python project using Flask for the web interface.

## Build, Test, and Lint Commands

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_agent.py

# Run a single test function
python -m pytest tests/test_agent.py::TestAgent::test_agent_creation

# Run tests matching a pattern
python -m pytest -k "test_agent"

# Run with coverage
python -m pytest tests/ --cov=hsim --cov-report=term-missing

# Run only unit tests (exclude slow/integration)
python -m pytest -m "not slow and not integration"

# Run only slow tests
python -m pytest -m "slow"
```

### Linting and Formatting

```bash
# Run pylint on the project
python -m pylint hsim/

# Run pylint on a specific file
python -m pylint hsim/core/agent/agent.py

# Format code with black
python -m black hsim/

# Check formatting without changes
python -m black --check hsim/
```

### Building the Package

```bash
# Install in development mode
pip install -e .

# Build the package
python setup.py build

# Create source distribution
python setup.py sdist
```

### Running the Application

```bash
# Run Flask web application
cd hsim/GSOM/flask
python app.py

# Run core simulation
python hsim/GSOM/GSOMGame.py
```

## Code Style Guidelines

### General Principles

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Keep functions focused and concise
- Add docstrings to public functions and classes

### Naming Conventions

- **Classes**: PascalCase (e.g., `Agent`, `Environment`, `FSM`)
- **Functions/Variables**: snake_case (e.g., `calculate_utilization`, `service_time`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_BUFFER_SIZE`)
- **Private methods/attributes**: prefix with underscore (e.g., `_linkFSM`, `_agents`)

### Type Hints

- Use type hints where appropriate for function parameters and return values
- Example:
  ```python
  def calculate_utilization(busy_time: float, total_time: float) -> float:
      """Calculate resource utilization percentage."""
      if total_time == 0:
          return 0.0
      return (busy_time / total_time) * 100
  ```

### Import Organization

- Standard library imports first
- Third-party imports second
- Local/application imports last
- Use absolute imports (e.g., `from hsim.core.agent.agent import Agent`)

### Code Formatting

- Maximum line length: 120 characters
- Indentation: 4 spaces (not tabs)
- Use trailing commas in multi-line collections
- Put imports on separate lines

### File Structure

```
hsim/
├── core/           # Core simulation framework
│   ├── agent/      # Agent base classes
│   ├── core/       # Environment, events, messages
│   ├── des/        # DES building blocks (Server, Buffer, etc.)
│   ├── fsm/        # Finite state machines
│   └── utils/      # Utilities and analysis tools
├── GSOM/           # Manufacturing simulation game
│   └── flask/      # Web application
├── tests/          # Test suite
└── ...
```

### Test Conventions

- Test files: `tests/test_*.py`
- Test classes: `Test*` (e.g., `class TestAgent(unittest.TestCase)`)
- Test methods: `test_*` (e.g., `def test_agent_creation(self)`)
- Use unittest framework (extends `unittest.TestCase`)
- Place tests in the `tests/` directory

### Error Handling

- Use specific exception types
- Include meaningful error messages
- Handle exceptions at appropriate levels
- Example:
  ```python
  if not hasattr(self, key):
      raise AttributeError(f"Attribute {key} does not exist in {self}.")
  ```

### Documentation

- Use docstrings for all public classes and functions
- Follow Google or NumPy docstring format
- Update README.md for user-facing changes
- Update CLAUDE.md for architecture changes
- Keep AGENTS.md updated with any process changes

### Configuration Files

- **pytest.ini**: Test configuration with markers (slow, integration, unit)
- **.pylintrc**: Linting rules (max-line-length=120, disables docstring checks)
- **setup.py**: Package configuration
- **requirements.txt**: Python dependencies

### Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes following these guidelines
3. Run tests to ensure nothing breaks
4. Run linting: `python -m pylint hsim/`
5. Format code: `python -m black hsim/`
6. Commit with clear messages
7. Push and create a Pull Request

### Key Patterns Used in This Project

- **Event-Driven Architecture**: Simulation driven by scheduled events
- **State Machine Pattern**: FSM integration for entity behaviors
- **Message Passing**: Asynchronous agent communication
- **Composition Over Inheritance**: Complex entities from simpler components
- **Observable Variables**: Reactive system with callback-based triggers (uses `<<` and `>>` operators)

### Important Notes

- The codebase uses path manipulation in some files for cross-platform compatibility
- Some internal attributes use underscore prefix (e.g., `_agents`, `_copy`)
- The Flask app uses SQLite for user management
- Simulation results can be exported to Excel files

### VS Code Settings

If using VS Code, the following settings are configured:
- Python extra paths for imports
- Type checking is off
- Pylint severity set to Hint
