import logging
from os import path

def get_argument(arguments, search_argument):
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


def validate_arguments(arguments):
    valid_arguments = True

    incoming_path = get_argument(arguments, ["--input", "-i"])
    output_path = get_argument(arguments, ["--output", "-o"])
    debug_enabled = get_argument(arguments, ["--debug", "-d"])
    dryrun_enabled = get_argument(arguments, ["--dryrun"])

    if incoming_path == False or output_path == False:
        valid_arguments = False

    if not path.exists(incoming_path):
        logging.error(f"Invalid incoming path: {incoming_path}")
        valid_arguments = False

    if not path.exists(output_path):
        logging.error(f"Invalid output path: {output_path}")
        valid_arguments = False

    if not valid_arguments:
        logging.error(f"Correct usage:")
        logging.error(f'{__file__} --input "c:\\some directory" --output c:\\myphotos')
        return False

    # convert Windows paths to Unix paths
    incoming_path = incoming_path.replace("\\", "/")
    output_path = output_path.replace("\\", "/")

    return_paths = {}
    return_paths["incoming_path"] = incoming_path
    return_paths["output_path"] = output_path

    if debug_enabled != False:
        if debug_enabled.lower() == "true":
            return_paths["debug"] = True
        elif debug_enabled.lower() == "false":
            return_paths["debug"] = False
        else:
            logging.error(f"Correct usage:")
            logging.error(
                f'{__file__} --input "c:\\some directory" --output c:\\myphotos --debug true'
            )
            # its not enough of an issue that it should stop execution
            return_paths["debug"] = False
    else:
        return_paths["debug"] = False

    if dryrun_enabled != False:
        if dryrun_enabled.lower() == "true":
            return_paths["dryrun"] = True
        elif dryrun_enabled.lower() == "false":
            return_paths["dryrun"] = False
        else:
            logging.error(f"Correct usage:")
            logging.error(
                f'{__file__} --input "c:\\some directory" --output c:\\myphotos --dryrun true'
            )
            # its not enough of an issue that it should stop execution
            return_paths["dryrun"] = False
    else:
        return_paths["dryrun"] = False

    return return_paths
