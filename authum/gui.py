import signal
import sys
from typing import Type, Union

import authum
import authum.util


HAS_TTY = sys.stdout.isatty()
HAS_TKINTER = False
try:
    import tkinter
    import tkinter.simpledialog as sdg

    HAS_TKINTER = True

    def prompt(prompt: str, type: Type = int) -> Union[None, str]:
        """Prompt for text"""
        tkinter.Tk().withdraw()
        return sdg.askstring(authum.metadata["Name"].capitalize(), prompt)

    def choose(prompt: str, choices: list) -> int:
        """Prompt for choice"""
        return ChoiceDialog(
            title=authum.metadata["Name"].capitalize(), prompt=prompt, choices=choices
        ).result

    class ChoiceDialog(sdg.Dialog):
        """Simple dialog box with a button for each choice"""

        def __init__(self, title: str, prompt: str, choices: list) -> None:
            self.prompt = prompt
            self.choices = choices

            root = tkinter.Tk()
            root.withdraw()
            super().__init__(parent=root, title=title)

        def body(self, master: tkinter.Tk) -> None:
            tkinter.Label(master, text=self.prompt, justify=tkinter.LEFT).pack()

        def buttonbox(self) -> None:
            box = tkinter.Frame(self)
            for i, choice in enumerate(self.choices):
                tkinter.Button(
                    box,
                    text=choice,
                    command=(lambda self=self, choice=i: self.make_choice(choice)),
                ).pack(side=tkinter.LEFT)
            box.pack()

            self.bind("<Return>", lambda event: self.make_choice(0))
            self.bind("<Escape>", lambda event: signal.raise_signal(signal.SIGINT))

        def make_choice(self, choice: int) -> None:
            self.result = choice
            self.ok()  # type: ignore

except ModuleNotFoundError as e:
    if not HAS_TTY:
        authum.util.rich_stderr.print(f"Warning: {e} (GUI prompts disabled)")

PROMPT_GUI = not HAS_TTY and HAS_TKINTER
