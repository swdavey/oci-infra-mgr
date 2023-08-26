import os
from pathlib import Path

class InfraArgsError(Exception):
    def __init__(self,message):
        super().__init__(message)


class InfraArgs(object):
    # Actions
    HELP = "HELP"
    START = "START"
    STOP = "STOP"

    # Logging levels
    CRITICAL = "CRITICAL"
    DEBUG = "DEBUG"
    ERROR = "ERROR"
    INFO = "INFO"
    WARNING = "WARNING"

    def __init__(self):
        self._action = self.HELP
        self._infra_file = None
        self._infra_log = None
        self._infra_log_level = None
        self._oci_cfg = None


    @property
    def action(self):
        return self._action

    @action.setter
    def action(self,action):
        uc_action = action.upper()
        if uc_action in (self.HELP, self.START, self.STOP):
            self._action = uc_action
        else:
            raise InfraArgsError("Unknown action {:s}.".format(action))


    @property
    def infra_file(self):
        return self._infra_file

    @infra_file.setter
    def infra_file(self,fname):
        if os.path.isfile(fname) and os.access(fname,os.R_OK):
            self._infra_file = fname
        else:
            raise InfraArgsError("Infrastructure file is not accessible, {:s}.".format(fname))


    @property
    def infra_log(self):
        return self._infra_log

    @infra_log.setter
    def infra_log(self,fname):
        if os.path.isfile(fname) and os.access(fname,os.W_OK):
            self._infra_log = fname
        else:
            raise InfraArgsError("Log file is not accessible, {:s}.".format(fname))


    @property
    def infra_log_level(self):
        return self._infra_log_level

    @infra_log_level.setter
    def infra_log_level(self,level):
        uc_level = level.upper()
        if uc_level in (self.CRITICAL, self.DEBUG, self.ERROR, self.INFO, self.WARNING):
            self._infra_log_level = uc_level
        else:
            raise InfraArgsError("Unknown logging level: {:s}.".format(level))


    @property
    def oci_cfg(self):
        return self._oci_cfg

    @oci_cfg.setter
    def oci_cfg(self,fname):
        if os.path.isfile(fname) and os.access(fname,os.R_OK):
            self._oci_cfg = fname
        else:
            raise InfraArgsError("OCI config file is not accessible, {:s}.".format(fname))
