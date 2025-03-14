from applications.applications import AppConfig
from wxflow import Configuration
from typing import Dict, Any


class GCAFSForecastOnlyAppConfig(AppConfig):
    '''
    Class to define GCAFS forecast-only configurations

    This class handles the configuration for GCAFS forecast-only runs, including
    aerosol initialization and forecast settings.

    Parameters
    ----------
    conf : Configuration
        Configuration object containing experiment settings

    Attributes
    ----------
    run : str
        Name of the run (default: 'gcafs')
    runs : list
        List of run names to process
    '''

    def __init__(self, conf: Configuration):
        super().__init__(conf)

        base = conf.parse_config('config.base')
        # print(f"Initializing GCAFS with base config: {base}")
        self.run = base.get('RUN', 'GCAFS').lower()  # Ensure lowercase
        self.runs = [self.run]
        # print(f"GCAFS runs set to: {self.runs}")

    def _get_run_options(self, conf: Configuration) -> Dict[str, Any]:
        '''
        Get GCAFS-specific run options by extending base run options

        Parameters
        ----------
        conf : Configuration
            Configuration object containing experiment settings

        Returns
        -------
        Dict[str, Any]
            Dictionary of run options with GCAFS-specific settings added
        '''

        run_options = super()._get_run_options(conf)

        # Force GCAFS-specific settings
        for run in self.runs:
            run_options[run].update({
                'do_aero_fcst': True,
                'do_aero_init': True,
                'do_aero': True,
                'exp_warm_start': conf.parse_config('config.base').get('EXP_WARM_START', False)
            })
            # print(f"Updated run options for {run}: {run_options[run]}")

        return run_options

    def _get_app_configs(self, run):
        '''
        Get list of config files required for GCAFS forecast-only workflow

        Parameters
        ----------
        run : str
            Name of the run to get configs for

        Returns
        -------
        list
            List of config file names required for this workflow
        '''

        # print(f"Getting app configs for run: {run}")
        configs = []
        options = self.run_options[run]

        if options['do_fetch_hpss'] or options['do_fetch_local']:
            configs += ['fetch']

        configs += ['stage_ic']

        # Add aerosol initialization step for GCAFS
        # print(options['do_aero_fcst'])
        if options['do_aero_fcst']:
            # print('here')
            configs += ['aerosol_init']

        configs += ['fcst', 'arch_vrfy', 'cleanup']

        if options['do_atm']:

            if options['do_upp'] or options['do_goes']:
                configs += ['upp']

            configs += ['atmos_products']

            # GCAFS handles aerosol initialization differently than GFS ATMA

            if options['do_tracker']:
                configs += ['tracker']

            if options['do_genesis']:
                configs += ['genesis']

            if options['do_genesis_fsu']:
                configs += ['genesis_fsu']

            if options['do_metp']:
                configs += ['metp']

            if options['do_bufrsnd']:
                configs += ['postsnd']

            if options['do_gempak']:
                configs += ['gempak']

            if options['do_awips']:
                configs += ['awips', 'fbwind']

        if options['do_ocean'] or options['do_ice']:
            configs += ['oceanice_products']

        if options['do_wave']:
            configs += ['waveinit', 'wavepostsbs', 'wavepostpnt']
            if options['do_wave_bnd']:
                configs += ['wavepostbndpnt', 'wavepostbndpntbll']
            if options['do_gempak']:
                configs += ['wavegempak']
            if options['do_awips']:
                configs += ['waveawipsbulls', 'waveawipsgridded']

        if options['do_mos']:
            configs += ['mos_stn_prep', 'mos_grd_prep', 'mos_ext_stn_prep', 'mos_ext_grd_prep',
                        'mos_stn_fcst', 'mos_grd_fcst', 'mos_ext_stn_fcst', 'mos_ext_grd_fcst',
                        'mos_stn_prdgen', 'mos_grd_prdgen', 'mos_ext_stn_prdgen', 'mos_ext_grd_prdgen',
                        'mos_wx_prdgen', 'mos_wx_ext_prdgen']

        if options['do_archcom']:
            configs += ['arch_tars']
            if options['do_globusarch']:
                configs += ['globus']

        return configs

    @staticmethod
    def _update_base(base_in):
        '''
        Update base configuration for GCAFS

        Parameters
        ----------
        base_in : dict
            Input base configuration

        Returns
        -------
        dict
            Updated base configuration with GCAFS-specific settings
        '''

        base_out = base_in.copy()
        base_out['RUN'] = 'GCAFS'

        return base_out

    def get_task_names(self):
        '''
        Get ordered list of task names for GCAFS workflow

        Returns
        -------
        Dict[str, list]
            Dictionary mapping run name to ordered list of task names
        '''

        options = self.run_options[self.run]

        tasks = []

        if options['do_fetch_hpss'] or options['do_fetch_local']:
            tasks += ['fetch']

        tasks += ['stage_ic']

        # Add aerosol initialization task for GCAFS
        if options['do_aero_fcst']:
            tasks += ['aerosol_init']

        if options['do_wave']:
            tasks += ['waveinit']
            # tasks += ['waveprep']  # TODO - verify if waveprep is executed in ...
            # ... forecast-only mode when APP=ATMW|S2SW

        tasks += ['fcst']

        if options['do_atm']:

            if options['do_upp']:
                tasks += ['atmupp']

            tasks += ['atmos_prod']

            if options['do_goes']:
                tasks += ['goesupp']

            if options['do_tracker']:
                tasks += ['tracker']

            if options['do_genesis']:
                tasks += ['genesis']

            if options['do_genesis_fsu']:
                tasks += ['genesis_fsu']

            if options['do_metp']:
                tasks += ['metp']

            if options['do_bufrsnd']:
                tasks += ['postsnd']

            if options['do_gempak']:
                tasks += ['gempak', 'gempakmeta']

            if options['do_awips']:
                tasks += ['awips_20km_1p0deg', 'fbwind']

        if options['do_ocean']:
            tasks += ['ocean_prod']

        if options['do_ice']:
            tasks += ['ice_prod']

        if options['do_wave']:
            if options['do_wave_bnd']:
                tasks += ['wavepostbndpnt', 'wavepostbndpntbll']
            tasks += ['wavepostsbs', 'wavepostpnt']
            if options['do_gempak']:
                tasks += ['wavegempak']
            if options['do_awips']:
                tasks += ['waveawipsbulls', 'waveawipsgridded']

        if options['do_mos']:
            tasks += ['mos_stn_prep', 'mos_grd_prep', 'mos_ext_stn_prep', 'mos_ext_grd_prep',
                      'mos_stn_fcst', 'mos_grd_fcst', 'mos_ext_stn_fcst', 'mos_ext_grd_fcst',
                      'mos_stn_prdgen', 'mos_grd_prdgen', 'mos_ext_stn_prdgen', 'mos_ext_grd_prdgen',
                      'mos_wx_prdgen', 'mos_wx_ext_prdgen']

        if options['do_archcom']:
            tasks += ['arch_tars']
            if options['do_globusarch']:
                tasks += ['globus_arch']

        tasks += ['arch_vrfy', 'cleanup']  # arch_tar, arch_vrfy, and cleanup **must** be the last tasks

        return {f"{self.run}": tasks}
