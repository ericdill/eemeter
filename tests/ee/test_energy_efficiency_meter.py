from datetime import datetime
import tempfile

import pytz
import pytest
import pandas as pd
import numpy as np

from eemeter.structures import (
    Project,
    ZIPCodeSite,
    EnergyTraceSet,
    EnergyTrace,
    Intervention,
    ModelingPeriodSet,
)
from eemeter.modeling.split import SplitModeledEnergyTrace
from eemeter.ee.meter import EnergyEfficiencyMeter
from eemeter.testing.mocks import MockWeatherClient
from eemeter.weather import TMY3WeatherSource


@pytest.fixture
def daily_data():
    index = pd.date_range('2012-01-01', periods=365*4, freq='D', tz=pytz.UTC)
    data = {
        "value": np.tile(1, (365 * 4,)),
        "estimated": np.tile(False, (365 * 4,))
    }
    return pd.DataFrame(data, index=index, columns=["value", "estimated"])


@pytest.fixture
def energy_trace_set(daily_data):
    energy_trace_set = EnergyTraceSet([
        EnergyTrace('ELECTRICITY_CONSUMPTION_SUPPLIED', data=daily_data,
                    unit='kWh'),
    ])
    return energy_trace_set


@pytest.fixture
def interventions():
    interventions = [
        Intervention(datetime(2014, 1, 1, tzinfo=pytz.UTC),
                     datetime(2014, 2, 1, tzinfo=pytz.UTC)),
    ]
    return interventions


@pytest.fixture
def project(energy_trace_set, interventions):
    site = ZIPCodeSite("02138")
    project = Project(energy_trace_set, interventions, site)
    return project


@pytest.fixture
def mock_tmy3_weather_source():
    tmp_dir = tempfile.mkdtemp()
    ws = TMY3WeatherSource("724838", tmp_dir, preload=False)
    ws.client = MockWeatherClient()
    ws._load_data()
    return ws


def test_basic_usage(project, mock_tmy3_weather_source):
    meter = EnergyEfficiencyMeter()
    results = meter.evaluate(project,
                             weather_normal_source=mock_tmy3_weather_source)

    assert isinstance(results['modeling_period_set'], ModelingPeriodSet)

    assert isinstance(results['modeled_energy_traces']['0'],
                      SplitModeledEnergyTrace)

    assert 'modeled_energy_trace_derivatives' in results

    project_derivatives = \
        results['project_derivatives'][('baseline', 'reporting')]
    assert project_derivatives['ELECTRICITY_ON_SITE_GENERATION_UNCONSUMED'] \
        is None
    assert project_derivatives['NATURAL_GAS_CONSUMPTION_SUPPLIED'] is None
    all_fuels = project_derivatives['ALL_FUELS_CONSUMPTION_SUPPLIED']
    elec = project_derivatives['ELECTRICITY_CONSUMPTION_SUPPLIED']

    assert all_fuels['unit'] == "KWH"
    assert elec['unit'] == "KWH"

    assert len(all_fuels['BASELINE']['annualized_weather_normal']) == 4
    assert len(all_fuels['REPORTING']['annualized_weather_normal']) == 4
    assert len(all_fuels['BASELINE']['gross_predicted']) == 4
    assert len(all_fuels['REPORTING']['gross_predicted']) == 4

    assert len(elec['BASELINE']['annualized_weather_normal']) == 4
    assert len(elec['REPORTING']['annualized_weather_normal']) == 4
    assert len(elec['BASELINE']['gross_predicted']) == 4
    assert len(elec['REPORTING']['gross_predicted']) == 4

    assert results['weather_source'].station == '994971'
    assert results['weather_normal_source'].station == '724838'
