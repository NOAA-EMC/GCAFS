#!/usr/bin/env python3

import os
from logging import getLogger
from typing import Dict, Any, Union, List
from pprint import pformat
import subprocess
from shutil import copyfile
import netCDF4

from wxflow import (AttrDict,
                    parse_j2yaml,
                    FileHandler,
                    Jinja,
                    logit,
                    Task,
                    add_to_datetime, to_timedelta,
                    WorkflowException,
                    Executable, which)

logger = getLogger(__name__.split('.')[-1])


class GCAFSInit(Task):
    """Aerosol Emissions pre-processing Task
    """

    @logit(logger, name="AerosolEmissions")
    def __init__(self, config: Dict[str, Any]) -> None:
        """Constructor for the Aerosol Emissions task

        Parameters
        ----------
        config : Dict[str, Any]
            Incoming configuration for the task from the environment

        Returns
        -------
        None
        """
        super().__init__(config)

        self.task_config = AttrDict(**self.task_config)
        
        logger.info(f"Read the gcafs_init configuration yaml file {self.task_config.gcafs_init}")

    @staticmethod
    @logit(logger)
    def initialize() -> None:
        """Initialize the work directory
        """

    @staticmethod
    @logit(logger)
    def configure() -> None:
        """Configure the artifacts in the work directory.
        Copy run specific data to run directory
        """

    @staticmethod
    @logit(logger)
    def merge_tile(base_file_name: str, append_file_name: str, tracers_to_append: List[str]) -> None:
        if not os.path.isfile(base_file_name):
            raise WorkflowException(f"Atmosphere file {base_file_name} does not exist!")

        if not os.path.isfile(append_file_name):
            raise WorkflowException(f"Chemistry file {append_file_name} does not exist!")

        append_file = netCDF4.Dataset(append_file_name, "r")
        base_file = netCDF4.Dataset(base_file_name, "r+")

        old_ntracer = base_file.dimensions["ntracer"].size
        new_ntracer = old_ntracer + len(tracers_to_append)

        # Copy over chemistry dimensions
        for dim_name in append_file.dimensions:
            base_file.createDimension(dim_name, append_file.dimensions[dim_name].size)

        for variable_name in tracers_to_append:
            logger.info(f"Adding variable {variable_name} to file")
            variable = append_file[variable_name]
            base_file.createVariable(variable_name, variable.datatype, variable.dimensions)
            base_file[variable_name][:] = variable[:]
            base_file[variable_name].setncatts(variable.__dict__)

        logger.info("Updating ntracer")
        subprocess.run(["ncks", "-x", "-v", "ntracer", "-O", base_file_name, base_file_name])
        base_file = netCDF4.Dataset(base_file_name, "r+")
        base_file.createDimension("ntracer", new_ntracer)

    @staticmethod
    @logit(logger)
    def execute(workdir: Union[str, os.PathLike], aprun_cmd: str) -> None:
        """Run the merge operation

        Parameters
        ----------
        workdir : str | os.PathLike
            work directory with the staged data
        aprun_cmd : str
            launcher command (not used for this task)
        """
        do_calc_increment = os.getenv('DO_CALC_INCREMENT', 'FALSE').upper() == 'TRUE'
        
        if not do_calc_increment:
            logger.info("DO_CALC_INCREMENT is not set to TRUE, skipping merge operation")
            return

        config = parse_j2yaml(f"{workdir}/config.yaml")
        
        atm_file = config.paths.atm_file
        chem_file = config.paths.chem_file
        variable_file = config.paths.tracer_list
        out_file = config.paths.get('out_file', atm_file)

        logger.info("DO_CALC_INCREMENT is TRUE, proceeding with merge operation")

        if out_file != atm_file:
            copyfile(atm_file, out_file)

        with open(variable_file, 'r') as f:
            variable_names = f.read().splitlines()

        AerosolEmissions.merge_tile(out_file, chem_file, variable_names)

    @staticmethod
    @logit(logger)
    def finalize() -> None:
        """Perform closing actions of the task.
        Copy data back from the DATA/ directory to COM/
        """
