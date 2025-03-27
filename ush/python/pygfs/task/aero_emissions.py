#!/usr/bin/env python3

import os
import re
import fnmatch
from matplotlib.pylab import f
import xarray as xr
from logging import getLogger
from typing import Dict, Any, Union
from dateutil.rrule import DAILY, rrule
from pprint import pformat

from wxflow import (AttrDict,
                    parse_j2yaml,
                    FileHandler,
                    logit,
                    Task,
                    to_timedelta,
                    WorkflowException,
                    Executable, which)

logger = getLogger(__name__.split('.')[-1])


class AeroEmission(Task):
    """Chemistry Emissions pre-processing Task
    """

    @logit(logger, name="AeroEmission")
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

        self.historical = bool(self.config.get('AERO_EMIS_FIRE_HIST', 0))
        nforecast_hours = self.task_config["FHMAX_GFS"]
        self.start_date = self.task_config["PDY"]
        self.end_date = self.start_date + to_timedelta(f'{nforecast_hours + 24}H')
        self.forecast_dates = list(rrule(freq=DAILY, dtstart=self.start_date, until=self.end_date))

        # # Extend task_config with localdict
        # self.task_config = AttrDict(**self.task_config, **localdict)

    @logit(logger)
    def initialize(self) -> None:
        """Initialize the work directory and process chemical emissions configuration.

        This method performs the following steps:
        1. Loads and parses the chem_emission.yaml.j2 template
        2. Sets up template variables for emission configuration
        3. Creates necessary working directories
        4. Copies required input files to working directory

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        WorkflowException
            If the YAML template file is not found
            If required directories cannot be created
            If file copying operations fail

        Notes
        -----
        The method expects the following configuration to be available:
        - HOMEgfs : str
            Base directory containing workflow configuration
        - DATA : str
            Working directory path
        - COMOUT_CHEM_HISTORY : str
            Output directory for chemical history files
        - AERO_EMIS_FIRE_DIR : str
            Directory containing fire emission data
        - AERO_EMIS_FIRE_VERSION : str
            Version of fire emission data (GBBEPx or QFED)

        The configuration is processed through a Jinja2 template system
        and the resulting setup is stored in self.task_config.
        """
        # Parse the YAML template
        yaml_template = os.path.join(self.config.HOMEgfs, 'parm/chem/chem_emission.yaml.j2')
        if not os.path.exists(yaml_template):
            msg = f'YAML template not found: {yaml_template}'
            logger.error(msg)
            raise WorkflowException(msg)

        if self.historical:
            logger.info(f'Processing historical emissions for {self.start_date} to {self.end_date}')

            # find the forecast dates that are in the historical period for the given emission dataset
            for dates in self.forecast_dates:
                if self.config.AERO_EMIS_FIRE.lower() == 'gbbepx':
                    files = self._find_gbbepx_files(dates, version=self.config.AERO_EMIS_FIRE_VERSION)
                elif self.config.AERO_EMIS_FIRE.lower() == 'qfed':
                    files = self._find_qfed_files(dates, version=self.config.AERO_EMIS_FIRE_VERSION)
        else:
            logger.info(f'Processing forecast emissions for {self.start_date}')

            if self.config.AERO_EMIS_FIRE.lower() == 'gbbepx':
                files = [self._find_gbbepx_files(self.start_date, version=self.config.AERO_EMIS_FIRE_VERSION)]
            elif self.config.AERO_EMIS_FIRE.lower() == 'qfed':
                files = [self._find_qfed_files(self.start_date, version=self.config.AERO_EMIS_FIRE_VERSION)]

        # Set up template variables
        tmpl_dict = {
            'DATA': self.config.DATA,
            'COMOUT_CHEM_HISTORY': self.config.COMOUT_CHEM_HISTORY,
            'AERO_EMIS_FIRE_DIR': self.config.AERO_EMIS_FIRE_DIR,
            'AERO_EMIS_FIRE_VERSION': self.config.AERO_EMIS_FIRE_VERSION,
            'historical': self.historical,
            'forecast_dates': self.config.get('forecast_dates', []),
            'qfed_vars': self.config.get('QFED_VARS',
                ["co", "nox", "so2", "nh3", "bc", "oc"]),
            'gbbepx_vars': self.config.get('GBBEPX_VARS',
                ["co", "nox", "so2", "nh3", "bc", "oc"]),
            "files_in": files
        }


        # Parse template and update task configuration
        logger.debug(f'Parsing YAML template: {yaml_template}')
        yaml_config = parse_j2yaml(yaml_template, tmpl_dict)
        self.task_config.update(yaml_config.get('chem_emission', {}))

        # Create directories
        for dir_path in self.task_config.data_in.mkdir:
            logger.info(f'Creating directory: {dir_path}')
            os.makedirs(dir_path, exist_ok=True)

        # Copy input files
        fh = FileHandler()
        for file_pair in self.task_config.data_in.copy:
            src = file_pair[0]
            dst = os.path.join(self.config.DATA, os.path.basename(src))
            logger.info(f'Copying {src} to {dst}')
            fh.copy(src, dst)

    @logit(logger)
    def _get_unique_months(self):
        """Extract unique months from forecast dates.

        This method finds all unique months present in the forecast dates
        range. Useful for monthly-based emissions processing.

        Returns
        -------
        set
            Set of unique months as zero-padded strings (01-12)

        Notes
        -----
        Uses self.forecast_dates which should be populated during initialization
        Months are returned as strings with leading zeros (e.g., '01' for January)
        """
        return set(f"{date.month:02d}" for date in self.forecast_dates)

    @logit(logger)
    def execute(self, workdir: Union[str, os.PathLike]) -> None:
        """Process emission files based on configuration.

        For GBBEPx files, converts them to COARDS compliant format and renames
        according to template pattern.

        Parameters
        ----------
        workdir : str | os.PathLike
            work directory with the staged data

        Returns
        -------
        None

        Notes
        -----
        Uses GBBEPX_TEMPLATE from config to rename processed files
        """
        logger.info(f"Processing emission files in {workdir}")

        if self.config.AERO_EMIS_FIRE.lower() == 'gbbepx':
            # Process each GBBEPx file
            for file_path in os.listdir(workdir):
                if file_path.startswith('GBBEPx'):
                    full_path = os.path.join(workdir, file_path)
                    logger.info(f"Processing GBBEPx file: {file_path}")

                    # Extract date from filename using regex
                    match = re.search(r"c(\d{8}).", file_path)
                    if not match:
                        logger.warning(f"Could not extract date from {file_path}, skipping")
                        continue

                    current_date = match.group(1)

                    # Convert to COARDS format
                    ds = self.GBBEPx_to_COARDS(full_path)

                    # Generate new filename from template
                    template = self.task_config.config.GBBEPX_TEMPLATE
                    new_name = template.replace('YYYYMMDD', current_date)
                    output_path = os.path.join(workdir, f"processed_{new_name}")

                    logger.info(f"Saving processed file to: {output_path}")
                    ds.to_netcdf(output_path)

        elif self.config.AERO_EMIS_FIRE.lower() == 'qfed':
            logger.info("QFED files do not require processing, skipping execute step")
            return

        logger.info("Emission processing complete")

    @logit(logger)
    def finalize(self) -> None:
        """Perform closing actions of the task.
        Copy processed files from the DATA directory to COMOUT_CHEM_HISTORY.

        Returns
        -------
        None

        Notes
        -----
        Only copies processed GBBEPx files or QFED files based on configuration
        Uses FileHandler for reliable file operations with logging
        """
        logger.info("Finalizing chemical emissions processing")

        fh = FileHandler()
        data_dir = self.config.DATA
        comout_dir = self.config.COMOUT_CHEM_HISTORY

        if self.config.AERO_EMIS_FIRE.lower() == 'gbbepx':
            pattern = "processed_GBBEPx*.nc"
        else:
            pattern = "qfed*.nc"

        processed_files = []
        for file_name in os.listdir(data_dir):
            if fnmatch.fnmatch(file_name, pattern):
                src = os.path.join(data_dir, file_name)
                dst = os.path.join(comout_dir, file_name)
                logger.info(f"Copying {src} to {dst}")
                fh.copy(src, dst)
                processed_files.append(file_name)

        self.task_config.update({'processed_files': processed_files})
        logger.info("Chemical emissions finalization complete")

    @logit(logger)
    def _find_gbbepx_files(self, dates, version='v5r0'):
        """Find GBBEPx files for the given date

        Parameters
        ----------
        dates : str
            Date for which to find GBBEPx files
        version : str
            Version of GBBEPx files to search for

        Returns
        -------
        List[str]
            List of GBBEPx files for the given date
        """
        logger.info(f'Finding GBBEPx files for {dates}')

        # Find all possible months
        months = self._get_unique_months()

        files_found = []
        # Find all possible files
        for mon in months:
            emis_file_dir = os.join(self.config.AERO_EMIS_FIRE_DIR, version, mon)
            all_files = os.listdir(emis_file_dir)

            matching_files = []

            pattern = r"s(\d{8})_e(\d{8})_c(\d{8})"

            for file_name in all_files:
                match = re.match(pattern, file_name)
                if match:
                    # start_date = match.group(1)
                    # end_date = match.group(2)
                    create_date = match.group(3)

                    if dates[0] <= create_date and dates[-1] <= create_date:
                        matching_files.append(file_name)
            files_found.extend(matching_files)

        return files_found

    @logit(logger)
    def _find_qfed_files(self, dates, vars, version='061'):
        """Find QFED files for the given date

        Parameters
        ----------
        dates : str
            Date for which to find GBBEPx files
        version : str
            Version of QFED files to search for

        Returns
        -------
        List[str]
            List of GBBEPx files for the given date
        """
        logger.info(f'Finding GBBEPx files for {dates}')

        # Find all possible months
        months = self._get_unique_months()

        files_found = []
        # Find all possible files
        for mon in months:
            for v in vars:
                emis_file_dir = os.join(self.config.AERO_EMIS_FIRE_DIR, version, mon)
                all_files = os.listdir(emis_file_dir)

                matching_files = []

                pattern = r"(\d{8}).nc"

                for file_name in all_files:
                    match = re.match(pattern, file_name)
                    if match:
                        create_date = match.group(1)

                        if dates[0] <= create_date and dates[-1] <= create_date:
                            matching_files.append(file_name)
                files_found.extend(matching_files)

        return files_found

    @logit(logger)
    def GBBEPx_to_COARDS(fname: Union[str, os.PathLike]) -> xr.Dataset:
        """Convert GBBEPx file to COARDS compliant format

        Parameters
        ----------
        fname : str | os.PathLike
            Input GBBEPx file path

        Returns
        -------
        xr.Dataset
            COARDS compliant dataset
        """
        logger.info(f"Converting {fname} to COARDS format")
        f = xr.open_dataset(fname, decode_cf=False)

        # Handle time dimension
        if 'Time' in f.dims:
            f = f.rename({"Time": 'time'})
        f.time.attrs['long_name'] = 'time'

        # Modify latitude and longitude attributes
        f = f.rename({'Longitude': 'lon', 'Latitude': 'lat'})

        # Validate and normalize coordinates
        # Check longitude range and monotonicity
        if not (f.lon.diff('lon') > 0).all():
            raise WorkflowException("Longitude values must be strictly increasing")

        # Ensure longitude is in [-180, 180] range
        f['lon'] = xr.where(f.lon > 180, f.lon - 360, f.lon)
        f = f.sortby('lon')  # Sort after potential wrapping

        # Check latitude monotonicity
        if not (f.lat.diff('lat') > 0).all():
            raise WorkflowException("Latitude values must be strictly increasing")

        f.lon.attrs.update({'long_name': 'Longitude', 'units': 'degrees_east'})
        f.lat.attrs.update({'long_name': 'Latitude', 'units': 'degrees_north'})

        # Remove Element dimension if present
        if 'Element' in f.dims:
            f = f.drop_dims('Element')

        # Update variable attributes
        for v in f.data_vars:
            if v not in ['FirePerc', 'QCAll', 'NumSensor', 'CloudPerc']:
                f[v].attrs['_FillValue'] = -9999.0
            elif v == 'FirePerc':
                f[v].attrs.update({'units': '-', 'long_name': 'percent_of_fire_in_grid_cell'})
            elif v == 'CloudPerc':
                f[v].attrs.update({'units': '-', 'long_name': 'percent_of_clouds_in_grid_cell'})
            elif v == 'NumSensor':
                f[v].attrs['units'] = '-'

        # Set global attributes
        f.attrs.update({'format': 'NetCDF', 'title': 'GBBEPx Fire Emissions'})

        return f