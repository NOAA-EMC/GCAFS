=====================================
Global Chemistry and Aerosol Forecast
=====================================

Overview
--------

The Global Chemistry and Aerosol Forecast System (GCAFS) extends the Global Forecast System (GFS)
with interactive aerosol and atmospheric chemistry capabilities. It provides a unified framework
for predicting the evolution of atmospheric composition alongside traditional weather variables.

Key Features
-----------

* Interactive GOCART aerosol module for forecasting dust, sea salt, sulfate, black carbon, and organic carbon
* Optional full atmospheric chemistry with gas-phase and heterogeneous reactions
* Integration with biomass burning emissions sources (QFED, GBBEPX)
* Aerosol-radiation-cloud interactions
* Optional aerosol data assimilation

Running GCAFS
------------

GCAFS can be run using the global-workflow framework. To set up a GCAFS experiment:

.. code-block:: bash

   ./setup_expt.py gcafs forecast-only --pslot my_gcafs_run --app ATMA \
                --idate 2023010100 --edate 2023010100 \
                --resdetatmos 384 --comroot /path/to/com --expdir /path/to/exp

Configuration is managed through the standard global-workflow configuration files. GCAFS-specific
settings are documented in :doc:`gcafs_config`.

After setting up the experiment, build the workflow XML and launch it:

.. code-block:: bash

   ./setup_xml.py /path/to/exp/my_gcafs_run
   cd /path/to/exp/my_gcafs_run
   rocotorun -w gcafs.xml -d gcafs.db

GCAFS Workflow
-------------

The GCAFS workflow includes these main tasks:

1. **stage_ic** - Stage initial conditions
2. **prep_emissions** - Prepare emissions data files
3. **aerosol_init** - Initialize aerosol fields
4. **fcst** - Run the UFS model with aerosols/chemistry
5. **atmos_prod** - Post-process atmosphere/aerosol output
6. **arch_vrfy** and **arch_tars** - Archive verification data and create tarballs

The workflow is managed by the Rocoto workflow manager, with tasks defined in the
``workflow/rocoto/gcafs_tasks.py`` file.

Output Products
--------------

GCAFS produces standard meteorological outputs plus aerosol fields including:

* Aerosol mass concentrations (dust, sea salt, sulfate, black carbon, organic carbon)
* Aerosol optical depth fields
* PM2.5 and PM10 concentrations
* Full chemical species concentrations when running with chemistry enabled

Output frequency is controlled by the standard global-workflow configuration options
in the same manner as GFS.
