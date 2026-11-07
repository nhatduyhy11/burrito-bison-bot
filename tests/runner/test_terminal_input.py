import asyncio
import os
import sys
import unittest
from unittest.mock import patch

from hauntedroom.runner.terminal_input import REINJECT_COMMAND, TerminalInput


@unittest.skipIf(os.name == "nt", "POSIX terminal integration")
class TerminalInputTest(unittest.IsolatedAsyncioTestCase):
    async def test_pipe_key_without_enter_and_restore_terminal(self):
        import pty
        import termios

        master, slave = pty.openpty()
        stream = os.fdopen(slave, "r")
        original = termios.tcgetattr(stream.fileno())
        queue = asyncio.Queue()
        reader = TerminalInput(asyncio.get_running_loop(), queue)
        try:
            with patch.object(sys, "stdin", stream):
                reader.start()
                os.write(master, b"x||")
                self.assertEqual(await asyncio.wait_for(queue.get(), 1), REINJECT_COMMAND)
                self.assertEqual(await asyncio.wait_for(queue.get(), 1), REINJECT_COMMAND)
                self.assertTrue(queue.empty())
                reader.close()
                restored = termios.tcgetattr(stream.fileno())
                mask = termios.ICANON | termios.ECHO | termios.ISIG
                self.assertEqual(restored[3] & mask, original[3] & mask)
                self.assertEqual(restored[6], original[6])
                self.assertFalse(reader._thread.is_alive())
        finally:
            reader.close()
            stream.close()
            os.close(master)
