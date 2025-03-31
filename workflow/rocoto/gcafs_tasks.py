"""
GCAFS (Global Chemistry and Aerosol Forecast System) Tasks module.

This module defines the tasks for the GCAFS workflow using Rocoto.
It provides task definitions for stage initialization, forecast,
post-processing, and archiving tasks.
"""
from applications.applications import AppConfig
from rocoto.tasks import Tasks
import rocoto.rocoto as rocoto
from wxflow import timedelta_to_HMS


class GCAFSTasks(Tasks):
    """
    Global Chemistry and Aerosol Forecast System (GCAFS) Tasks class.

    This class defines tasks for the GCAFS workflow, including
    initialization, forecast, post-processing, and product generation tasks.

    Parameters
    ----------
    app_config : AppConfig
        Application configuration object
    run : str
        Run type identifier (e.g., 'gcafs', 'gfs')
    """

    def __init__(self, app_config: AppConfig, run: str) -> None:
        """
        Initialize the GCAFSTasks class.

        Parameters
        ----------
        app_config : AppConfig
            Application configuration object
        run : str
            Run type identifier

        Returns
        -------
        None
        """
        # Here we ensure we're using 'gcafs' as the run type internally
        if run == 'gfs':
            run = 'gcafs'

        super().__init__(app_config, run)

    def stage_ic(self):
        """
        Create a task for staging initial conditions.

        This task prepares the initial conditions needed for the forecast run.

        Returns
        -------
        str
            XML representation of the task
        """

        resources = self.get_resource('stage_ic')
        task_name = f'{self.run}_stage_ic'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/stage_ic.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }
        task = rocoto.create_task(task_dict)

        return task

    def waveinit(self):
        """
        Create a task for wave initialization.

        This task initializes the wave component of the model.

        Returns
        -------
        str
            XML representation of the task
        """

        resources = self.get_resource('waveinit')
        task_name = f'{self.run}_wave_init'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/waveinit.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }
        task = rocoto.create_task(task_dict)

        return task

    def prep_emissions(self):
        """
        Create a task for preparing emissions data.

        This task prepares the emissions data needed for aerosol forecasting.

        Returns
        -------
        str
            XML representation of the task
        """

        resources = self.get_resource('prep_emissions')
        task_name = f'{self.run}_prep_emissions'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/prep_emissions.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }
        task = rocoto.create_task(task_dict)

        return task


    def aerosol_init(self):
        """
        Create a task for aerosol initialization.

        This task initializes the aerosol component, setting up the necessary
        files and conditions for the aerosol forecast.

        Returns
        -------
        str
            XML representation of the task
        """
        input_path = self._template_to_rocoto_cycstring(self._base['COM_ATMOS_INPUT_TMPL'])
        restart_path = self._template_to_rocoto_cycstring(self._base['COM_ATMOS_RESTART_TMPL'])

        deps = []
        # Files from current cycle
        ntiles = self._base['ntiles']
        files = ['gfs_ctrl.nc'] + [f'gfs_data.tile{tile}.nc' for tile in range(1, ntiles + 1)]
        for file in files:
            data = f'{input_path}/{file}'
            dep_dict = {'type': 'data', 'data': data}
            deps.append(rocoto.add_dependency(dep_dict))

        # Calculate offset based on RUN = gcafs | gdas
        interval = None
        if self.run in ['gcafs']:
            interval = self._base['interval_gfs']
        elif self.run in ['gdas']:
            interval = self._base['interval']
        offset = timedelta_to_HMS(-interval)

        # Files from previous cycle
        files = ['@Y@m@d.@H0000.fv_core.res.nc'] + \
                [f'@Y@m@d.@H0000.fv_core.res.tile{tile}.nc' for tile in range(1, ntiles + 1)] + \
                [f'@Y@m@d.@H0000.fv_tracer.res.tile{tile}.nc' for tile in range(1, ntiles + 1)]

        for file in files:
            data = [f'{restart_path}/', file]
            dep_dict = {'type': 'data', 'data': data, 'offset': [offset, None]}
            deps.append(rocoto.add_dependency(dep_dict))

        dependencies = rocoto.create_dependency(dep_condition='and', dep=deps)

        cycledef = f'{self.run}_seq'
        resources = self.get_resource('aerosol_init')
        task_name = f'{self.run}_aerosol_init'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': self.envars,
                     'cycledef': cycledef,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/aerosol_init.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        task = rocoto.create_task(task_dict)

        return task

    def fcst(self):
        """
        Create a task for the deterministic forecast.

        This task runs the deterministic forecast (member 000) for all forecast segments.
        It depends on stage_ic and optionally on wave_init, prep_emissions, and aerosol_init
        if these components are enabled.

        Returns
        -------
        str
            XML representation of the task
        """
        dependencies = []
        dep_dict = {'type': 'task', 'name': f'{self.run}_stage_ic'}
        dependencies.append(rocoto.add_dependency(dep_dict))

        if self.options['do_wave']:
            dep_dict = {'type': 'task', 'name': f'{self.run}_wave_init'}
            dependencies.append(rocoto.add_dependency(dep_dict))

        if self.options['do_aero_fcst']:
            dep_dict = {'type': 'task', 'name': f'{self.run}_prep_emissions'}
            dependencies.append(rocoto.add_dependency(dep_dict))
            dep_dict = {'type': 'task', 'name': f'{self.run}_aerosol_init'}
            dependencies.append(rocoto.add_dependency(dep_dict))

        dependencies = rocoto.create_dependency(dep_condition='and', dep=dependencies)

        num_fcst_segments = len(self.options['fcst_segments']) - 1

        fcst_vars = self.envars.copy()
        fcst_envars_dict = {'FCST_SEGMENT': '#seg#'}
        for key, value in fcst_envars_dict.items():
            fcst_vars.append(rocoto.create_envar(name=key, value=str(value)))

        resources = self.get_resource('fcst')
        task_name = f'{self.run}_fcst_mem000_seg#seg#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': fcst_vars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/fcst.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        seg_var_dict = {'seg': ' '.join([f"{seg}" for seg in range(0, num_fcst_segments)])}
        metatask_dict = {'task_name': f'{self.run}_fcst_mem000',
                         'is_serial': True,
                         'var_dict': seg_var_dict,
                         'task_dict': task_dict
                         }

        task = rocoto.create_task(metatask_dict)

        return task

    def efcs(self):
        """
        Create tasks for the ensemble forecast members.

        This task runs the ensemble forecast members (001-N) for all forecast segments.
        It depends on stage_ic and optionally on wave_init and prep_emissions
        if these components are enabled.

        Returns
        -------
        str
            XML representation of the task
        """
        dependencies = []
        dep_dict = {'type': 'task', 'name': f'{self.run}_stage_ic'}
        dependencies.append(rocoto.add_dependency(dep_dict))

        if self.options['do_wave']:
            dep_dict = {'type': 'task', 'name': f'{self.run}_wave_init'}
            dependencies.append(rocoto.add_dependency(dep_dict))

        if self.options['do_aero_fcst']:
            dep_dict = {'type': 'task', 'name': f'{self.run}_prep_emissions'}
            dependencies.append(rocoto.add_dependency(dep_dict))

        dependencies = rocoto.create_dependency(dep_condition='and', dep=dependencies)

        num_fcst_segments = len(self.options['fcst_segments']) - 1
        resources = self.get_resource('efcs')

        # Kludge to work around bug in rocoto with serial metatasks nested
        #   in a parallel one (see christopherwharrop/rocoto#109). For now,
        #   loop over member to create a separate metatask for each instead
        #   of a metatask of a metatask.
        #
        tasks = []
        for member in [f"{mem:03d}" for mem in range(1, self.nmem + 1)]:

            efcsenvars = self.envars.copy()
            efcsenvars_dict = {'ENSMEM': f'{member}',
                               'MEMDIR': f'mem{member}',
                               'FCST_SEGMENT': '#seg#'
                               }
            for key, value in efcsenvars_dict.items():
                efcsenvars.append(rocoto.create_envar(name=key, value=str(value)))

            task_name = f'{self.run}_fcst_mem{member}_seg#seg#'
            task_dict = {'task_name': task_name,
                         'resources': resources,
                         'dependency': dependencies,
                         'envars': efcsenvars,
                         'cycledef': self.run,
                         'command': f'{self.HOMEgfs}/jobs/rocoto/fcst.sh',
                         'job_name': f'{self.pslot}_{task_name}_@H',
                         'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                         'maxtries': '&MAXTRIES;'
                         }

            seg_var_dict = {'seg': ' '.join([f"{seg}" for seg in range(0, num_fcst_segments)])}
            seg_metatask_dict = {'task_name': f'{self.run}_fcst_mem{member}',
                                 'is_serial': True,
                                 'var_dict': seg_var_dict,
                                 'task_dict': task_dict
                                 }

            tasks.append(rocoto.create_task(seg_metatask_dict))

        return '\n'.join(tasks)

        # Keeping this in hopes the kludge is no longer necessary at some point
        #
        # member_var_dict = {'member': ' '.join([f"{mem:03d}" for mem in range(1, self.nmem + 1)])}
        # mem_metatask_dict = {'task_name': f'{self.run}_fcst_ens',
        #                      'is_serial': False,
        #                      'var_dict': member_var_dict,
        #                      'task_dict': seg_metatask_dict
        #                      }

        # task = rocoto.create_task(mem_metatask_dict)

        # return task

    def atmos_prod(self):
        """
        Create a task for atmospheric product generation.

        This task generates products from the atmospheric component output.

        Returns
        -------
        str
            XML representation of the task
        """
        return self._atmosoceaniceprod('atmos')

    def ocean_prod(self):
        """
        Create a task for ocean product generation.

        This task generates products from the ocean component output.

        Returns
        -------
        str
            XML representation of the task
        """
        return self._atmosoceaniceprod('ocean')

    def ice_prod(self):
        """
        Create a task for ice product generation.

        This task generates products from the ice component output.

        Returns
        -------
        str
            XML representation of the task
        """
        return self._atmosoceaniceprod('ice')

    def _atmosoceaniceprod(self, component: str):
        """
        Create a task for atmospheric, oceanic, or ice product generation.

        This is a helper method used by atmos_prod, ocean_prod, and ice_prod methods.

        Parameters
        ----------
        component : str
            Component name ('atmos', 'ocean', or 'ice')

        Returns
        -------
        str
            XML representation of the task
        """

        fhout_ocn_gfs = self._configs['base']['FHOUT_OCN_GFS']
        fhout_ice_gfs = self._configs['base']['FHOUT_ICE_GFS']
        products_dict = {'atmos': {'config': 'atmos_products',
                                   'history_path_tmpl': 'COM_ATMOS_MASTER_TMPL',
                                   'history_file_tmpl': f'{self.run}.t@Hz.master.grb2f#fhr3_last#'},
                         'ocean': {'config': 'oceanice_products',
                                   'history_path_tmpl': 'COM_OCEAN_HISTORY_TMPL',
                                   'history_file_tmpl': f'{self.run}.ocean.t@Hz.{fhout_ocn_gfs}hr_avg.f#fhr3_next#.nc'},
                         'ice': {'config': 'oceanice_products',
                                 'history_path_tmpl': 'COM_ICE_HISTORY_TMPL',
                                 'history_file_tmpl': f'{self.run}.ice.t@Hz.{fhout_ice_gfs}hr_avg.f#fhr3_last#.nc'}}

        component_dict = products_dict[component]
        config = component_dict['config']
        history_path_tmpl = component_dict['history_path_tmpl']
        history_file_tmpl = component_dict['history_file_tmpl']

        max_tasks = self._configs[config]['MAX_TASKS']
        resources = self.get_resource(config)

        fhrs = self._get_forecast_hours(self.run, self._configs[config], component)

        # when replaying, atmos component does not have fhr 0, therefore remove 0 from fhrs
        is_replay = self._configs[config]['REPLAY_ICS']
        if is_replay and component in ['atmos'] and 0 in fhrs:
            fhrs.remove(0)

        # ocean/ice components do not have fhr 0 as they are averaged output
        if component in ['ocean', 'ice'] and 0 in fhrs:
            fhrs.remove(0)

        fhr_var_dict = self.get_grouped_fhr_dict(fhrs=fhrs, ngroups=max_tasks)

        # Adjust walltime based on the largest group
        largest_group = max([len(grp.split(',')) for grp in fhr_var_dict['fhr_list'].split(' ')])
        resources['walltime'] = Tasks.multiply_HMS(resources['walltime'], largest_group)

        history_path = self._template_to_rocoto_cycstring(self._base[history_path_tmpl], {'MEMDIR': 'mem#member#'})
        deps = []
        data = f'{history_path}/{history_file_tmpl}'
        dep_dict = {'type': 'data', 'data': data, 'age': 120}
        deps.append(rocoto.add_dependency(dep_dict))
        dep_dict = {'type': 'task', 'name': f'{self.run}_fcst_mem#member#_#seg_dep#'}
        deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps, dep_condition='or')

        postenvars = self.envars.copy()
        postenvar_dict = {'ENSMEM': '#member#',
                          'MEMDIR': 'mem#member#',
                          'FHR_LIST': '#fhr_list#',
                          'COMPONENT': component}
        for key, value in postenvar_dict.items():
            postenvars.append(rocoto.create_envar(name=key, value=str(value)))

        task_name = f'{self.run}_{component}_prod_mem#member#_#fhr_label#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': postenvars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/{config}.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'}

        fhr_metatask_dict = {'task_name': f'{self.run}_{component}_prod_#member#',
                             'task_dict': task_dict,
                             'var_dict': fhr_var_dict}

        member_var_dict = {'member': ' '.join([f"{mem:03d}" for mem in range(0, self.nmem + 1)])}
        member_metatask_dict = {'task_name': f'{self.run}_{component}_prod',
                                'task_dict': fhr_metatask_dict,
                                'var_dict': member_var_dict}

        task = rocoto.create_task(member_metatask_dict)

        return task

    def atmos_ensstat(self):
        """
        Create a task for atmospheric ensemble statistics.

        This task computes statistical products from ensemble atmospheric output.

        Returns
        -------
        str
            XML representation of the task
        """

        resources = self.get_resource('atmos_ensstat')

        deps = []
        for member in range(0, self.nmem + 1):
            task = f'{self.run}_atmos_prod_mem{member:03d}_#fhr_label#'
            dep_dict = {'type': 'task', 'name': task}
            deps.append(rocoto.add_dependency(dep_dict))

        dependencies = rocoto.create_dependency(dep_condition='and', dep=deps)

        fhrs = self._get_forecast_hours(self.run, self._configs['atmos_ensstat'])

        # when replaying, atmos component does not have fhr 0, therefore remove 0 from fhrs
        is_replay = self._configs['atmos_ensstat']['REPLAY_ICS']
        if is_replay and 0 in fhrs:
            fhrs.remove(0)

        max_tasks = self._configs['atmos_ensstat']['MAX_TASKS']
        fhr_var_dict = self.get_grouped_fhr_dict(fhrs=fhrs, ngroups=max_tasks)

        # Adjust walltime based on the largest group
        largest_group = max([len(grp.split(',')) for grp in fhr_var_dict['fhr_list'].split(' ')])
        resources['walltime'] = Tasks.multiply_HMS(resources['walltime'], largest_group)

        postenvars = self.envars.copy()
        postenvar_dict = {'FHR_LIST': '#fhr_list#'}
        for key, value in postenvar_dict.items():
            postenvars.append(rocoto.create_envar(name=key, value=str(value)))

        task_name = f'{self.run}_atmos_ensstat_#fhr_label#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': postenvars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/atmos_ensstat.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'}

        fhr_metatask_dict = {'task_name': f'{self.run}_atmos_ensstat',
                             'task_dict': task_dict,
                             'var_dict': fhr_var_dict}

        task = rocoto.create_task(fhr_metatask_dict)

        return task

    def wavepostsbs(self):
        """
        Create a task for wave post-processing on a grid.

        This task performs post-processing of wave model output on a spatial grid.

        Returns
        -------
        str
            XML representation of the task
        """

        wave_grid = self._configs['base']['waveGRD']
        history_path = self._template_to_rocoto_cycstring(self._base['COM_WAVE_HISTORY_TMPL'], {'MEMDIR': 'mem#member#'})
        history_file = f'/{self.run}wave.out_grd.{wave_grid}.@Y@m@d.@H@M@S'

        deps = []
        dep_dict = {'type': 'data', 'data': [history_path, history_file], 'offset': [None, '#fhr3_next#:00:00']}
        deps.append(rocoto.add_dependency(dep_dict))
        dep_dict = {'type': 'task', 'name': f'{self.run}_fcst_mem#member#_#seg_dep#'}
        deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps, dep_condition='or')

        fhrs = self._get_forecast_hours(self.run, self._configs['wavepostsbs'], 'wave')

        # When using replay, output does not start until hour 3
        is_replay = self._configs['wavepostsbs']['REPLAY_ICS']
        if is_replay:
            fhrs = [fhr for fhr in fhrs if fhr not in [0, 1, 2]]

        max_tasks = self._configs['wavepostsbs']['MAX_TASKS']
        fhr_var_dict = self.get_grouped_fhr_dict(fhrs=fhrs, ngroups=max_tasks)

        wave_post_envars = self.envars.copy()
        postenvar_dict = {'ENSMEM': '#member#',
                          'MEMDIR': 'mem#member#',
                          'FHR_LIST': '#fhr_list#',
                          }
        for key, value in postenvar_dict.items():
            wave_post_envars.append(rocoto.create_envar(name=key, value=str(value)))

        resources = self.get_resource('wavepostsbs')

        # Adjust walltime based on the largest group
        largest_group = max([len(grp.split(',')) for grp in fhr_var_dict['fhr_list'].split(' ')])
        resources['walltime'] = Tasks.multiply_HMS(resources['walltime'], largest_group)

        task_name = f'{self.run}_wave_post_grid_mem#member#_#fhr_label#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': wave_post_envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/wavepostsbs.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        fhr_metatask_dict = {'task_name': f'{self.run}_wave_post_grid_#member#',
                             'task_dict': task_dict,
                             'var_dict': fhr_var_dict}

        member_var_dict = {'member': ' '.join([f"{mem:03d}" for mem in range(0, self.nmem + 1)])}
        member_metatask_dict = {'task_name': f'{self.run}_wave_post_grid',
                                'task_dict': fhr_metatask_dict,
                                'var_dict': member_var_dict}

        task = rocoto.create_task(member_metatask_dict)

        return task

    def wavepostbndpnt(self):
        """
        Create a task for wave post-processing at boundary points.

        This task performs post-processing of wave model output at boundary points.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        dep_dict = {'type': 'metatask', 'name': f'{self.run}_fcst_mem#member#'}
        deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps)

        wave_post_bndpnt_envars = self.envars.copy()
        postenvar_dict = {'ENSMEM': '#member#',
                          'MEMDIR': 'mem#member#',
                          }
        for key, value in postenvar_dict.items():
            wave_post_bndpnt_envars.append(rocoto.create_envar(name=key, value=str(value)))

        resources = self.get_resource('wavepostbndpnt')
        task_name = f'{self.run}_wave_post_bndpnt_mem#member#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': wave_post_bndpnt_envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/wavepostbndpnt.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        member_var_dict = {'member': ' '.join([str(mem).zfill(3) for mem in range(0, self.nmem + 1)])}
        member_metatask_dict = {'task_name': f'{self.run}_wave_post_bndpnt',
                                'task_dict': task_dict,
                                'var_dict': member_var_dict
                                }

        task = rocoto.create_task(member_metatask_dict)

        return task

    def wavepostbndpntbll(self):
        """
        Create a task for wave post-processing at boundary points bulletin.

        This task generates bulletin products from wave model output at boundary points.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        atmos_hist_path = self._template_to_rocoto_cycstring(self._base["COM_ATMOS_HISTORY_TMPL"], {'MEMDIR': 'mem#member#'})

        # The wavepostbndpntbll job runs on forecast hours up to FHMAX_WAV_IBP
        last_fhr = self._configs['wave']['FHMAX_WAV_IBP']

        data = f'{atmos_hist_path}/{self.run}.t@Hz.atm.logf{last_fhr:03d}.txt'
        dep_dict = {'type': 'data', 'data': data}
        deps.append(rocoto.add_dependency(dep_dict))

        dep_dict = {'type': 'metatask', 'name': f'{self.run}_fcst_mem#member#'}
        deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep_condition='or', dep=deps)

        wave_post_bndpnt_bull_envars = self.envars.copy()
        postenvar_dict = {'ENSMEM': '#member#',
                          'MEMDIR': 'mem#member#',
                          }
        for key, value in postenvar_dict.items():
            wave_post_bndpnt_bull_envars.append(rocoto.create_envar(name=key, value=str(value)))

        resources = self.get_resource('wavepostbndpntbll')
        task_name = f'{self.run}_wave_post_bndpnt_bull_mem#member#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': wave_post_bndpnt_bull_envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/wavepostbndpntbll.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        member_var_dict = {'member': ' '.join([str(mem).zfill(3) for mem in range(0, self.nmem + 1)])}
        member_metatask_dict = {'task_name': f'{self.run}_wave_post_bndpnt_bull',
                                'task_dict': task_dict,
                                'var_dict': member_var_dict
                                }

        task = rocoto.create_task(member_metatask_dict)

        return task

    def wavepostpnt(self):
        """
        Create a task for wave post-processing at specific points.

        This task performs post-processing of wave model output at specific points of interest.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        dep_dict = {'type': 'metatask', 'name': f'{self.run}_fcst_mem#member#'}
        deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_wave_bnd']:
            dep_dict = {'type': 'task', 'name': f'{self.run}_wave_post_bndpnt_bull_mem#member#'}
            deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep_condition='and', dep=deps)

        wave_post_pnt_envars = self.envars.copy()
        postenvar_dict = {'ENSMEM': '#member#',
                          'MEMDIR': 'mem#member#',
                          }
        for key, value in postenvar_dict.items():
            wave_post_pnt_envars.append(rocoto.create_envar(name=key, value=str(value)))

        resources = self.get_resource('wavepostpnt')
        task_name = f'{self.run}_wave_post_pnt_mem#member#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': wave_post_pnt_envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/wavepostpnt.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        member_var_dict = {'member': ' '.join([str(mem).zfill(3) for mem in range(0, self.nmem + 1)])}
        member_metatask_dict = {'task_name': f'{self.run}_wave_post_pnt',
                                'task_dict': task_dict,
                                'var_dict': member_var_dict
                                }

        task = rocoto.create_task(member_metatask_dict)

        return task

    def extractvars(self):
        """
        Create a task for extracting variables from model output.

        This task extracts specific variables from the model output for further processing.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        if self.options['do_wave']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_grid_#member#'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_ocean']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_ocean_prod_#member#'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_ice']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_ice_prod_#member#'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_atm']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_atmos_prod_#member#'}
            deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep_condition='and', dep=deps)
        extractvars_envars = self.envars.copy()
        extractvars_dict = {'ENSMEM': '#member#',
                            'MEMDIR': 'mem#member#',
                            }
        for key, value in extractvars_dict.items():
            extractvars_envars.append(rocoto.create_envar(name=key, value=str(value)))

        resources = self.get_resource('extractvars')
        task_name = f'{self.run}_extractvars_mem#member#'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'dependency': dependencies,
                     'envars': extractvars_envars,
                     'cycledef': self.run,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/extractvars.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        member_var_dict = {'member': ' '.join([str(mem).zfill(3) for mem in range(0, self.nmem + 1)])}
        member_metatask_dict = {'task_name': f'{self.run}_extractvars',
                                'task_dict': task_dict,
                                'var_dict': member_var_dict
                                }

        task = rocoto.create_task(member_metatask_dict)

        return task

    def arch_vrfy(self):
        """
        Create a task for archiving verification data.

        This task archives data used for verification of model performance.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        dep_dict = {'type': 'metatask', 'name': f'{self.run}_atmos_prod'}
        deps.append(rocoto.add_dependency(dep_dict))
        dep_dict = {'type': 'metatask', 'name': f'{self.run}_atmos_ensstat'}
        deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_ice']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_ice_prod'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_ocean']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_ocean_prod'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_wave']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_grid'}
            deps.append(rocoto.add_dependency(dep_dict))
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_pnt'}
            deps.append(rocoto.add_dependency(dep_dict))
            if self.options['do_wave_bnd']:
                dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_bndpnt'}
                deps.append(rocoto.add_dependency(dep_dict))
                dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_bndpnt_bull'}
                deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_extractvars']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_extractvars'}
            deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps, dep_condition='and')

        resources = self.get_resource('arch_vrfy')
        task_name = f'{self.run}_arch_vrfy'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': self.run,
                     'dependency': dependencies,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/arch_vrfy.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        task = rocoto.create_task(task_dict)

        return task

    def arch_tars(self):
        """
        Create a task for creating archive tar files.

        This task creates tar archives of model output data for long-term storage.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        dep_dict = {'type': 'metatask', 'name': f'{self.run}_atmos_prod'}
        deps.append(rocoto.add_dependency(dep_dict))
        dep_dict = {'type': 'metatask', 'name': f'{self.run}_atmos_ensstat'}
        deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_ice']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_ice_prod'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_ocean']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_ocean_prod'}
            deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_wave']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_grid'}
            deps.append(rocoto.add_dependency(dep_dict))
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_pnt'}
            deps.append(rocoto.add_dependency(dep_dict))
            if self.options['do_wave_bnd']:
                dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_bndpnt'}
                deps.append(rocoto.add_dependency(dep_dict))
                dep_dict = {'type': 'metatask', 'name': f'{self.run}_wave_post_bndpnt_bull'}
                deps.append(rocoto.add_dependency(dep_dict))
        if self.options['do_extractvars']:
            dep_dict = {'type': 'metatask', 'name': f'{self.run}_extractvars'}
            deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps, dep_condition='and')

        resources = self.get_resource('arch_tars')
        task_name = f'{self.run}_arch_tars'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': self.run,
                     'dependency': dependencies,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/arch_tars.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        task = rocoto.create_task(task_dict)

        return task

    def globus(self):
        """
        Create a task for Globus transfer.

        This task manages the transfer of data using Globus.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        dep_dict = {'type': 'task', 'name': f'{self.run}_arch_vrfy'}
        deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps)

        resources = self.get_resource('globus')
        task_name = 'globus_arch'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': 'gefs',
                     'dependency': dependencies,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/globus_arch.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        task = rocoto.create_task(task_dict)

        return task

    def cleanup(self):
        """
        Create a task for cleanup operations.

        This task performs cleanup operations after the workflow is complete.

        Returns
        -------
        str
            XML representation of the task
        """
        deps = []
        if self.options['do_archcom']:
            if self.options['do_globusarch']:
                dep_dict = {'type': 'task', 'name': f'{self.run}_globus_arch'}
            else:
                dep_dict = {'type': 'task', 'name': f'{self.run}_arch_tars'}
            deps.append(rocoto.add_dependency(dep_dict))
            dependencies = rocoto.create_dependency(dep=deps)

        dep_dict = {'type': 'task', 'name': 'gefs_arch_vrfy'}
        deps.append(rocoto.add_dependency(dep_dict))
        dependencies = rocoto.create_dependency(dep=deps, dep_condition='and')

        resources = self.get_resource('cleanup')
        task_name = f'{self.run}_cleanup'
        task_dict = {'task_name': task_name,
                     'resources': resources,
                     'envars': self.envars,
                     'cycledef': self.run,
                     'dependency': dependencies,
                     'command': f'{self.HOMEgfs}/jobs/rocoto/cleanup.sh',
                     'job_name': f'{self.pslot}_{task_name}_@H',
                     'log': f'{self.rotdir}/logs/@Y@m@d@H/{task_name}.log',
                     'maxtries': '&MAXTRIES;'
                     }

        task = rocoto.create_task(task_dict)

        return task
