#!/usr/bin/env python
import os
import json
import datetime
import argcomplete
import argparse
from typing import List, Dict
from enum import Enum, auto


from message import load_message, write_message, view_message, new_message, prompt_message, remove_message, detach_message, append_message, cut_message
from editor import edit_message, include_file, execute_command, convert_text_base64, edit_content_message, edit_role_message
from utils import Colors, quit_program, count_tokens, export_messages
from api import save_config, update_config, api_config, full_model_choices
from ll_email import send_email
from web import process_web_request

#from logcmd_llt_branch_1 import search_messages, export_messages_to_markdown

class ArgKey(Enum):
    LL_FILE = auto()
    DETACH = auto()
    FILE_INCLUDE = auto()
    PROMPT = auto()
    EXPORT = auto()
    ROLE = auto()
    EXEC = auto()
    WEB = auto()
    EMAIL = auto()
    NON_INTERACTIVE = auto()


plugins = {
    'load': load_message,
    'write': write_message,
    'view': view_message,
    'new': new_message,
    'prompt': prompt_message,
    'edit': edit_message,
    'file': include_file,
    'quit': quit_program,
    'remove': remove_message,
    'detach': detach_message,
    'append': append_message,
    'cut': cut_message
}

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    def get_ll_files(prefix: str, parsed_args: argparse.Namespace, **kwargs) -> List[str]:
        ll_dir = parsed_args.ll_dir if parsed_args.ll_dir else os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir'])
        return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

    parser.add_argument('--ll_file', '-l', type=str, help="Language log file. List of natural language messages stored as JSON.", default="").completer = get_ll_files
    parser.add_argument('--file_include', '-f', type=str, help="Read content from a file and include it in the ll.", default="")
    parser.add_argument('--image_path', type=str, default="")

    parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")

    parser.add_argument('--model', '-m', type=str, help="Specify model.", default="gpt-4-turbo", choices=full_model_choices)
    parser.add_argument('--temperature', '-t', type=float, help="Specify temperature.", default=0.9)
    
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output, up to the specified number of tokens.", default=0)
    parser.add_argument('--top_p', type=float, help="Sample from top P tokens.", default=1.0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['cmd_dir']))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['exec_dir']))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir']))

    parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")

    # All plugin flags here
    parser.add_argument('--detach', action='store_true', help="Pop last message from given ll.")
    parser.add_argument('--export', action='store_true', help="Export messages to a file.")
    parser.add_argument('--exec', action='store_true', help="Execute the last message")
    parser.add_argument('--view', action='store_true', help="Print the last message.")

    parser.add_argument('--email', action='store_true', help="Send an email with the last message.")
    parser.add_argument('--web', action='store_true', help="Fetch a web page and filter tags between paragraphs and code blocks.")

    argcomplete.autocomplete(parser)
    return parser.parse_args()

def init_directories(args: argparse.Namespace) -> None:
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def log_command(command: str, messages: list, args: dict) -> None:
    tokens = count_tokens(messages, args) if messages else 0
    log_path = os.path.join(args['cmd_dir'], os.path.splitext(args['ll_file'])[0] + ".log")
    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(messages, indent=2)}\n")  
        logfile.write(f"args: {json.dumps(vars(args), indent=2)}\n")
        logfile.write(f"command: {command}\n")
        logfile.write(f"input: TO IMPLEMENT\n")
        logfile.write(f"after_command: {json.dumps(messages[-1], indent=2)}\n")
        logfile.write(f"tokens: {tokens}\n")
        logfile.write(f"COMMAND_END\n\n")

def help_message(messages: List[Dict], args: argparse.Namespace) -> List[Dict]:
    print("Available commands:")
    combined_commands = get_combined_commands()
    for command, func in combined_commands.items():
        #docstring = func.__doc__.split('\n')[0] if func.__doc__ else 'No description available'
        print(f"{command}: {func}")
    return messages

test_commands = {
    'h': help_message, 
    'b': convert_text_base64,
    'x': execute_command,
    'sc': save_config,
    'uc': update_config,
    'er': edit_role_message,
    'ec': edit_content_message,
    'email': send_email,
    'web': process_web_request}

def get_combined_commands():
    combined_commands = {**plugins, **test_commands}
    return combined_commands

def main() -> None:
    args = parse_arguments()
    init_directories(args)
    messages = list()

    arg_to_function = {
        ArgKey.LL_FILE: load_message,
        ArgKey.FILE_INCLUDE: include_file,
        ArgKey.PROMPT: new_message,
        ArgKey.DETACH: detach_message,
        ArgKey.EXPORT: export_messages,
        ArgKey.EXEC: execute_command,
        ArgKey.WEB: process_web_request,
        ArgKey.EMAIL: send_email
    }

    for arg_key, func in arg_to_function.items():
        if getattr(args, arg_key.name.lower(), None):
            messages = func(messages, args)

    if getattr(args, ArgKey.NON_INTERACTIVE.name.lower()):
        messages = prompt_message(messages.append({'role': 'user', 'content': args.prompt}), args)
        if getattr(args, ArgKey.LL_FILE.name.lower()):
            write_message(messages, args)
        quit_program(messages, args)
    if getattr(args, "view"):
        print(messages[-1]['content'])

    Colors.print_header()
    greeting = f"Hello {os.getenv('USER')}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")
    command_map = {**get_combined_commands(), **{command[0]: func for command, func in plugins.items() if command[0] not in plugins}}
    print(command_map)
    while True:
        try:
            cmd = input('llt> ')
            if cmd in command_map:
                messages = command_map[cmd](messages, args)
                if not cmd.startswith('v'): log_command(cmd, messages, vars(args))
            else:
                messages.append({'role': args.role, 'content': f"{cmd}"})
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    main()
