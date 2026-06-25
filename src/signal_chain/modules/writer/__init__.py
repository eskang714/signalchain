from signal_chain.modules.writer.core import clear_registry, register, render_message
from signal_chain.modules.writer.markdown import handle as _md_handle

register("md", _md_handle)

__all__ = ["clear_registry", "register", "render_message"]
