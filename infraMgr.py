import getopt
import json
import logging
import oci
import sys
from infraArgs import InfraArgs
from infraArgs import InfraArgsError


DEFAULT_INFRASTRUCTURE_FILE = "./infra.json"
DEFAULT_LOG_FILE = "/var/log/infra/infra.log"

# Constants derived from the type names used in the INFRASTRUCTURE_FILE
COMPUTE_CLIENT = "compute_instance"
MYSQL_HEATWAVE = "mysql_database"

# Global object to handle logging throughout the program
logger = None


def switch_compute(oci_cfg,ocid,compartment,action):
    compute_client_mgr = oci.core.ComputeClient(oci_cfg)
    compute_instance = compute_client_mgr.get_instance(ocid)
    if action == InfraArgs.START:
        if compute_instance.data.lifecycle_state == oci.core.models.Instance.LIFECYCLE_STATE_STOPPED:
            compute_client_mgr.instance_action(ocid,action="START")
            logger.info("Request sent to start compute instance {:s} in compartment {:s}".format(compute_instance.data.display_name,compartment))
        else:
            logger.warning("Compute instance {:s} in compartment {:s} is in a {:s} state. It must be in a STOPPED state before it can be started.".format(compute_instance.data.display_name,compartment,compute_instance.data.lifecycle_state))
    elif action == InfraArgs.STOP:
        if compute_instance.data.lifecycle_state == oci.core.models.Instance.LIFECYCLE_STATE_RUNNING:
            compute_client_mgr.instance_action(ocid,action="STOP")
            logger.info("Request sent to stop compute instance {:s} in compartment {:s}".format(compute_instance.data.display_name,compartment))
        else:
            logger.warning("Compute instance {:s} in compartment {:s} is in a {:s} state. It must be in a RUNNING state before it can be stopped.".format(compute_instance.data.display_name,compartment,compute_instance.data.lifecycle_state))
    else:
        logger.error("Unknown action, {:s}, requested for compute instance {:s} in compartment {:s}".format(action,compute_instance.data.display_name,compartment))
    return


def switch_mysql(oci_cfg,ocid,compartment,action):
    db_client_mgr = oci.mysql.DbSystemClient(oci_cfg)
    db_instance = db_client_mgr.get_db_system(ocid)
    if action == InfraArgs.START:
        if db_instance.data.lifecycle_state == oci.mysql.models.DbSystem.LIFECYCLE_STATE_INACTIVE:
            db_client_mgr.start_db_system(ocid)
            logger.info("Request sent to start MySQL database instance {:s} in compartment {:s}".format(db_instance.data.display_name,compartment))
        else:
            logger.warning("MySQL database instance {:s} in compartment {:s} is in a {:s} state. It must be in an INACTIVE (stopped) state before it can be started.".format(db_instance.data.display_name,compartment,db_instance.data.lifecycle_state))
    elif action == InfraArgs.STOP:
        if db_instance.data.lifecycle_state == oci.mysql.models.DbSystem.LIFECYCLE_STATE_ACTIVE:
            shutdown_details = oci.mysql.models.StopDbSystemDetails(
                shutdown_type = oci.mysql.models.StopDbSystemDetails.SHUTDOWN_TYPE_FAST)
            db_client_mgr.stop_db_system(ocid,shutdown_details)
            logger.info("Request sent to stop MySQL database instance {:s} in compartment {:s}".format(db_instance.data.display_name,compartment))
        else:
            logger.warning("MySQL database instance {:s} in compartment {:s} is in a {:s} state. It must be in an ACTIVE (started) state before it can be stopped.".format(db_instance.data.display_name, compartment,db_instance.data.lifecycle_state))
    else:
        logger.error("Unknown action, {:s}, requested for MySQL database instance {:s} in compartment {:s}".format(action,db_instance.data.display_name,compartment))
    return


def process_infrastructure(infra,action,oci_cfg):
    for compartment in infra['compartments']:
        for obj in compartment['objects']:
            if obj['exclude'] == True:
                logger.info("{:s} {:s} in compartment {:s} has been excluded.".format(obj['type'],obj['name'],compartment['name']))
                continue
            if obj['type'] == COMPUTE_CLIENT:
                switch_compute(oci_cfg,obj['ocid'],compartment['name'],action)
            elif obj['type'] == MYSQL_HEATWAVE:
                switch_mysql(oci_cfg,obj['ocid'],compartment['name'],action)
            else:
                logger.error("Attempt to process and unknown type, {:s}".format(obj['type']))
    return


def process_cmd_line(args):
    arg_handler = InfraArgs()
    arguments, values = getopt.getopt(args,"ha:a:o:i:l:v:", ["help","action=","oci-cfg=","infra-file=","logfile=","level="])
    for current_arg, current_val in arguments:
        if current_arg in ("-h","--help"):
            arg_handler.action = InfraArgs.HELP
            break
        elif current_arg in ("-a","--action"):
            arg_handler.action = current_val
        elif  current_arg in ("-i","--infra-file"):
            arg_handler.infra_file = current_val
        elif current_arg in ("-l","--logfile"):
            arg_handler.infra_log = current_val
        elif current_arg in ("-v","--level"):
            arg_handler.infra_log_level = current_val
        elif current_arg in ("-o","--oci-cfg"):
            arg_handler.oci_cfg = current_val
        else:
            arg_handler.action = None
            break

    return arg_handler


def usage():
    print("\n  Usage:")
    print("  =====")
    print("""
  There are two modes of usage: seeking help and performing an action. When
  performing an action you must specify the action and optionally provide
  further flags and arguments as shown.
  """)
    print("  {:s} -h\n".format(sys.argv[0]))
    print("  {:s} -a <action> [-i <infrastructure-file> -l <logfile> -v <log-level> -o <oci-config-file>]".format(sys.argv[0]))
    print("""
  Modal Flags
  -----------

  -h | --help

  Displays this page. If help is requested then this page will be displayed
  regardless of any other actions being requested or flags used.

  -a | --action <START|STOP>

  The argument to the action flag must be either START or STOP.

  Optional Flags
  --------------

  The following flags only have relevance if the action flag is used.

  -i | --infra-file <infrastructure-file>

  Where infrastructure-file includes both the path and name of the file.
  For example, /root/infra.json where infra.json is the file name.
  If this option is not used then the program will look for a file called,
  infra.json, in the current working directory.

  This file must be readable by the program.

  -o | --oci-cfg <oci-config-file>

  Where oci-config-file includes both the path and name of the file.
  For example, /root/config where config is the file name.
  If this option is not used then the program will attempt to read this
  file in the default location for the underlying OS, e.g. for Oracle
  Linux this will be /<user-home-dir>/.oci/config

  This file must be readable by the program.

  -l | --logfile <logfile>

  For example the path could be /root/infra.log where infra.log is the file
  name. If this option is not used then the program will write this log to
  the following default location, /var/log/infra/infra.log

  This file must be both readable and writable by the program.

  -v | --level <DEBUG|INFO|WARNING|ERROR|CRITICAL>

  The argument to the log-level flag must be one of the options shown. The
  options are in order of verbosity with DEBUG providing the most output.
  If this option is not used then the program will default to logging at
  the INFO level (will log all events except those pertaining to DEBUG).

  """)
    return


def configure_logging(filename,level):
    global logger

    logfile = DEFAULT_LOG_FILE
    if filename is not None:
        logfile = filename

    if level is not None:
        if level == InfraArgs.CRITICAL:
            log_level = logging.CRITICAL
        elif level == InfraArgs.DEBUG:
            log_level = logging.DEBUG
        elif level == InfraArgs.ERROR:
            log_level = logging.ERROR
        elif level == InfraArgs.INFO:
            log_level = logging.INFO
        elif level == InfraArgs.WARNING:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
    else:
        log_level = logging.INFO

    logging.basicConfig(filename=logfile, format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger()
    logger.setLevel(log_level)
    return


def get_infrastructure(filename):
    infra_filename = DEFAULT_INFRASTRUCTURE_FILE
    if filename is not None:
        infra_filename = filename
    file_handle = open(infra_filename)
    infra = json.load(file_handle)
    file_handle.close()
    return infra


def get_oci_cfg(oci_cfg_file):
    oci_cfg = oci.config.from_file()
    if oci_cfg_file is not None:
        oci_cfg = oci.config.from_file(args.oci_cfg)
    return oci_cfg


def main(cmd_line_args):
    global logger

    try:
        args = process_cmd_line(cmd_line_args[1:])
        if args.action == InfraArgs.HELP:
            usage()
        else:
            configure_logging(args.infra_log,args.infra_log_level)
            logger.info("*********** Commencing run *************")
            logger.info("Command line: {:s}".format(" ".join(cmd_line_args)))
            infra = get_infrastructure(args.infra_file)
            oci_cfg = get_oci_cfg(args.oci_cfg)
            process_infrastructure(infra,args.action,oci_cfg)
            logger.info("Run completed successfully.")
    except Exception as e:
        if logger is not None:
            logger.critical("Run ended abnormally with exception: {:s}".format(str(e)))
        else:
            # If an exception occurs before the logger is configured then print to stderr
            print("Run ended abnormally with exception: {:s}".format(str(e)),file=sys.stderr)
        sys.exit(1)

    return

# Program entry point
if __name__ == "__main__":
    main(sys.argv)