from loguru import logger
from inquirer import prompt, List, Confirm
from typing import Optional


class ModeChoice:
    """Выбор режима"""

    def __init__(self, mode_type: str, soft_id: int, name: str):
        self.type = mode_type
        self.soft_id = soft_id
        self.name = name

    def __repr__(self):
        return self.name


def choose_mode() -> ModeChoice:
    """Выбрать режим работы софта"""

    logger.info("=" * 60)
    logger.info("🤖 ETHEREAL TRADING BOT")
    logger.info("=" * 60)

    options = [
        # Database modes
        ("➕ Create New Database (Single Accounts)", "database", 101),
        ("➕ Create New Database (Delta-Neutral Groups)", "database", 102),

        # Trading modes
        ("🎯 Mode 1: Futures Market", "module", 1),
        ("📊 Mode 2: Futures Limits", "module", 2),
        ("🔗 Mode 3: Pair Futures Limits (Delta-Neutral)", "module", 3),
        ("❌ Mode 4: Cancel All Orders & Positions", "module", 4),
        ("📈 Mode 5: Parse Statistics", "module", 5),
    ]

    # Преобразовать в формат для inquirer
    choices = [opt[0] for opt in options]

    questions = [
        List(
            'mode',
            message='Select mode:',
            choices=choices,
        ),
    ]

    try:
        answer = prompt(questions)
        selected_name = answer['mode']

        for opt_name, opt_type, opt_id in options:
            if opt_name == selected_name:
                logger.info(f"\n✓ Selected: {opt_name}\n")
                return ModeChoice(opt_type, opt_id, opt_name)

    except (KeyboardInterrupt, EOFError):
        raise KeyboardInterrupt()


def confirm_action(message: str) -> bool:
    """Подтвердить действие"""
    questions = [
        Confirm(
            'confirm',
            message=message,
            default=True,
        ),
    ]

    try:
        answer = prompt(questions)
        return answer.get('confirm', False)
    except (KeyboardInterrupt, EOFError):
        return False
