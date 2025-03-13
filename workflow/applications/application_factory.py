from wxflow import Factory
from applications.gfs_cycled import GFSCycledAppConfig
from applications.gfs_forecast_only import GFSForecastOnlyAppConfig
from applications.gefs import GEFSAppConfig
from applications.sfs import SFSAppConfig
from applications.gcafs_forecast_only import GCAFSForecastOnlyAppConfig

app_config_factory = Factory('AppConfig')
app_config_factory.register('gfs_cycled', GFSCycledAppConfig)
app_config_factory.register('gfs_forecast-only', GFSForecastOnlyAppConfig)
app_config_factory.register('gefs_forecast-only', GEFSAppConfig)
app_config_factory.register('sfs_forecast-only', SFSAppConfig)
# Register both formats for GCAFS forecast-only
app_config_factory.register('gcafs_forecast-only', GCAFSForecastOnlyAppConfig)
app_config_factory.register('forecast-only_gcafs', GCAFSForecastOnlyAppConfig)
