from contextmesh.packets.schema import CommandResultPacket
from contextmesh.wrappers.test_runner import distill_command_output, parse_pytest_output


def test_parse_pytest_output_captures_assertion_message():
    sample = """============================= test session starts ==============================
collected 1 item

tests/test_something.py F                                                [100%]

=================================== FAILURES ===================================
___________________________ test_my_failing_function ___________________________

    def test_my_failing_function():
>       assert False == True
E       AssertionError: assert False == True

tests/test_something.py:4: AssertionError
=========================== short test summary info ============================
FAILED tests/test_something.py::test_my_failing_function - AssertionError
============================== 1 failed in 0.05s ===============================
"""
    packet = parse_pytest_output("pytest", 1, sample)

    assert isinstance(packet, CommandResultPacket)
    assert packet.status == "failed"
    assert len(packet.failures) == 1
    failure = packet.failures[0]
    assert failure.test == "test_my_failing_function"
    assert failure.file == "tests/test_something.py"
    assert failure.line == 4
    assert failure.assertion == "AssertionError: assert False == True"
    assert "\\n" not in failure.minimal_trace
    assert "assert False == True" in failure.minimal_trace


def test_jest_output_distillation():
    sample = """ FAIL  src/__tests__/foo.test.ts
  ✕ adds two numbers (3 ms)

  ● adds two numbers

    expect(received).toBe(expected)

    Expected: 4
    Received: 5

      at Object.<anonymous> (src/__tests__/foo.test.ts:10:20)

Tests: 1 failed, 1 total
"""
    packet = distill_command_output(["npm", "test"], 1, sample)
    assert packet.status == "failed"
    assert len(packet.failures) == 1
    failure = packet.failures[0]
    assert "adds two numbers" in failure.test
    assert failure.file.endswith("foo.test.ts")
    assert failure.line == 10


def test_generic_command_truncates_output():
    long = "x" * 5000
    packet = distill_command_output(["weird-command"], 2, long)
    assert packet.status == "failed"
    assert len(packet.failures) == 1
    assert len(packet.failures[0].minimal_trace) <= 1000
