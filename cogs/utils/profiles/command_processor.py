import re


class CommandProcessor(object):

    COMMAND_REGEX = re.compile(
        r'^{{.+?}}$',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE
    )
    VALID_COMMAND_REGEX = re.compile(
        r'''
        {{
            DEFAULT\s*(?<!\\)\"(?P<default>.+?)(?<!\\)\"
            (\s*
                (?P<command>
                    (?P<commandname>HASROLE|HASANYROLE|FIELDVALUE)\(
                        (?P<commandparams>(?:\d{16,23}(?:,\s*)?)+|(?:(?<!\\)\".+(?<!\\)\"(?:,\s*)?)+)
                    \)\s*SAYS\s*(?<!\\)\"(?P<text>.+?)(?<!\\)\"
                )
            )+
        }}
        ''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE
    )
    COMMAND_PARAMETERS_REGEX = re.compile(
        r'''
        (?P<command>
            (?P<commandname>HASROLE|HASANYROLE|FIELDVALUE)\(
                (?P<commandparams>(?:\d{16,23}(?:,\s*)?)+|(?:(?<!\\)\".+(?<!\\)\"(?:,\s*)?)+)
            \)\s*SAYS\s*(?<!\\)\"(?P<text>.+?)(?<!\\)\"
        )
        ''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE
    )
