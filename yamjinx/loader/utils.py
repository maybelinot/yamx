from jinja2.sandbox import SandboxedEnvironment

from yamjinx.constants import NON_EXISTING_STR


def get_jinja_env():
    env = SandboxedEnvironment(
        # variable parsing is disabled this way
        variable_start_string=NON_EXISTING_STR,
        variable_end_string=NON_EXISTING_STR,
        # yaml parsing relies on this configuration
        trim_blocks=True,
    )
    env.filters = {}
    env.globals = {}
    return env
