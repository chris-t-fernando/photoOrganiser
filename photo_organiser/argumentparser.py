import logging
from os import path


class ArgumentParserInputPathNotValid(Exception):
    # exception thrown when the input path does not exist
    def __init__(self, input_path):
        super().__init__(self, f"{input_path}: Input path does not exist")


class ArgumentParserOutputPathNotValid(Exception):
    # exception thrown when the output path does not exist
    def __init__(self, output_path):
        super().__init__(self, f"{output_path}: Output path does not exist")


class ArgumentParser:
    arguments: list = None
    incoming_path: str = None
    output_path: str = None
    debug: bool = False
    dryrun: bool = False
    valid_arguments: bool = True

    def __init__(self, arguments):
        self.arguments = arguments

        incoming_path = self.get_argument(arguments, ["--input", "-i"])
        output_path = self.get_argument(arguments, ["--output", "-o"])
        debug_enabled = self.get_argument(arguments, ["--debug", "-d"])
        dryrun_enabled = self.get_argument(arguments, ["--dryrun"])

        if incoming_path == False or output_path == False:
            self.valid_arguments = False

        if not path.exists(incoming_path):
            logging.error(f"Invalid incoming path: {incoming_path}")
            self.valid_arguments = False
            raise ArgumentParserInputPathNotValid(incoming_path)

        if not path.exists(output_path):
            logging.error(f"Invalid output path: {output_path}")
            self.valid_arguments = False
            raise ArgumentParserOutputPathNotValid(output_path)

        if not self.valid_arguments:
            logging.error(f"Correct usage:")
            logging.error(
                f'{__file__} --input "c:\\some directory" --output c:\\myphotos'
            )
            return

        # convert Windows paths to Unix paths
        incoming_path = incoming_path.replace("\\", "/")
        output_path = output_path.replace("\\", "/")

        self.incoming_path = incoming_path
        self.output_path = output_path

        if debug_enabled != False:
            if debug_enabled.lower() == "true":
                self.debug = True
            elif debug_enabled.lower() == "false":
                self.debug = False
            else:
                logging.error(f"Correct usage:")
                logging.error(
                    f'{__file__} --input "c:\\some directory" --output c:\\myphotos --debug true'
                )
                # its not enough of an issue that it should stop execution
                self.debug = False
        else:
            self.debug = False

        if dryrun_enabled != False:
            if dryrun_enabled.lower() == "true":
                self.dryrun = True
            elif dryrun_enabled.lower() == "false":
                self.dryrun = False
            else:
                logging.error(f"Correct usage:")
                logging.error(
                    f'{__file__} --input "c:\\some directory" --output c:\\myphotos --dryrun true'
                )
                # its not enough of an issue that it should stop execution
                self.dryrun = False
        else:
            self.dryrun = False

        self.valid_arguments = True

    def get_argument(self, arguments: list, search_argument: list) -> bool:
        found = False
        for s in search_argument:
            if s in arguments:
                try:
                    logging.debug(
                        f"Found argument {search_argument}.  Value is {arguments[arguments.index(s)+1]}"
                    )
                    return arguments[arguments.index(s) + 1]
                except Exception as e:
                    return False

        return False
