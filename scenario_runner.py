#!/usr/bin/python3

"""System energy modelling and battery lifetime estimation tool.

This is a custom system (and subsystem) energy consumption modelling tool.
It takes as an input a YAML file specifying what components and/or subsystems
are to be included, as well as what power source is used.

Based on that information, the script that calcualtes expected energy
consumption over two pre-defined time periods - one hour and one day.

Finally, using the data on the power source, most often a battery, it estimates
how long the battery would last given that the pattern of energy consumption
does not change. This estimate takes into account the End-of-Life capacity,
as well as a margin specified in the battery YAML file.

    Typical usage example:

    $ python scenario_runner.py -h
    $ python scenario_runner.py --scenario scenario_file.yml
"""

# TODO: Add comments and documentation
# TODO: LaTeX reporting
# TODO: Graphical reporting

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pint
import yaml


__author__ = 'Viktor Doychinov'
__copyright__ = 'Copyright 2020, Pipebots'
__license__ = 'MIT'
__version__ = '1.0.0'
__maintainer__ = 'Viktor Doychinov'
__email__ = 'eenvdo@leeds.ac.uk'
__status__ = 'Development'
__date__ = '2020-02-04'

ureg = pint.UnitRegistry()


class Subsystem(object):
    """
    Sets subsystem parameters as class attributes. Checks important things are
    present. Does getters and setters to avoid oops-es. Converts strings to
    units, enabled by `pint'.

    Raises errors if voltages or currents are invalid or missing.
    Rest is optional.
    """

    required_params = ['voltage', 'on_current', 'standby_current',
                       'sleep_current', 'part_number', 'vendor']

    required_cycles = ['on_duty_cycle', 'standby_duty_cycle', 'time_period']

    def __init__(self, subsystem_filename=None, duty_cycles=None):
        if subsystem_filename is None:
            raise RuntimeError('Please provide a subsystem YAML filename')

        if duty_cycles is None or not isinstance(duty_cycles, dict):
            raise RuntimeError('Please provide duty cycles info dict')

        global ureg

        try:
            with open(subsystem_filename, 'r') as yaml_input_file:
                params = yaml.safe_load(yaml_input_file)
        except IOError as error:
            raise RuntimeError('Error opening file {}, check filename'.
                               format(subsystem_filename)). \
                               with_traceback(error.__traceback__)
        except yaml.YAMLError as error:
            raise RuntimeError('File {} contains invalid YAML syntax'.
                               format(subsystem_filename)). \
                               with_traceback(error.__traceback__)
        else:
            if not all(param in params for param in
                       Subsystem.required_params):
                raise RuntimeError('Required parameter missing in YAML file')

            if not all(param in duty_cycles for param in
                       Subsystem.required_cycles):
                raise RuntimeError('Required timing information missing')

        try:
            params['voltage'] = ureg.parse_expression(params['voltage'])
            params['on_current'] = ureg.parse_expression(params['on_current'])
            params['standby_current'] = ureg.parse_expression(
                                        params['standby_current']
                                        )
            params['sleep_current'] = ureg.parse_expression(
                                      params['sleep_current']
                                      )
            duty_cycles['time_period'] = ureg.parse_expression(
                                         duty_cycles['time_period']
                                         )

            duty_cycles['on_duty_cycle'] = float(duty_cycles['on_duty_cycle'])
            duty_cycles['standby_duty_cycle'] = float(duty_cycles['standby_'
                                                                  'duty_'
                                                                  'cycle'])
        except pint.UndefinedUnitError as error:
            raise RuntimeError('Check units syntax'). \
                               with_traceback(error.__traceback__)
        except ValueError as error:
            raise RuntimeError('Provide duty cycles as numbers'). \
                               with_traceback(error.__traceback__)

        self.vendor = params['vendor']
        self.part_number = params['part_number']
        self._voltage = params['voltage']
        self._on_cur = params['on_current']
        self._stby_cur = params['standby_current']
        self._sleep_cur = params['sleep_current']
        self._period = params['time_period']
        self._on_cycle = duty_cycles['on_duty_cycle'] / 100.0
        self._stby_cycle = duty_cycles['standby_duty_cycle'] / 100.0
        self._sleep_cycle = 1.0 - (self._on_cycle + self._stby_cycle)

        if round(self._sleep_cycle) <= 0.0:
            raise ValueError('Duty cycles need to sum up to 100%')

    def _update_sleep_cycle(self):
        self._sleep_cycle = 1.0 - (self._on_cycle + self._stby_cycle)

        if round(self._sleep_cycle) <= 0.0:
            raise ValueError('Duty cycles need to sum up to 100%')

    def on_energy_consumption(self, time_period=None):
        if time_period is None:
            time_period = self.time_period

        energy = self.voltage * self.on_current * self.on_duty_cycle
        energy = energy * time_period

        return energy

    def standby_energy_consumption(self, time_period=None):
        if time_period is None:
            time_period = self.time_period

        energy = self.voltage * self.standby_current * self.standby_duty_cycle
        energy = energy * time_period

        return energy

    def sleep_energy_consumption(self, time_period=None):
        if time_period is None:
            time_period = self.time_period

        energy = self.voltage * self.sleep_current * self.sleep_duty_cycle
        energy = energy * time_period

        return energy

    def total_energy_consumption(self, time_period=None):
        if time_period is None:
            time_period = self.time_period

        energy = (self.on_energy_consumption(time_period) +
                  self.standby_energy_consumption(time_period) +
                  self.sleep_energy_consumption(time_period))

        return energy

    @property
    def time_period(self):
        return self._period

    @time_period.setter
    def time_period(self, new_period):
        global ureg

        try:
            new_period = ureg.parse_expression(new_period)
        except pint.UndefinedUnitError as error:
            raise ValueError('Invalid unit syntax'). \
                             with_traceback(error.__traceback__)

        if isinstance(new_period, float) or isinstance(new_period, int):
            raise ValueError('No units specified')

        self._period = new_period

    @property
    def on_duty_cycle(self):
        return self._on_cycle

    @on_duty_cycle.setter
    def on_duty_cycle(self, new_cycle):
        try:
            new_cycle = float(new_cycle)
            new_cycle /= 100.0
        except ValueError as error:
            raise ValueError('Variable type needs to be int, float, or str'). \
                            with_traceback(error.__traceback__)

        self._on_cycle = new_cycle

        try:
            self._update_sleep_cycle()
        except ValueError as error:
            raise RuntimeError('Invalid combination of duty cycles,'
                               'need to sum up to 100%'). \
                                with_traceback(error.__traceback__)

    @property
    def standby_duty_cycle(self):
        return self._stby_cycle

    @standby_duty_cycle.setter
    def standby_duty_cycle(self, new_cycle):
        try:
            new_cycle = float(new_cycle)
            new_cycle /= 100.0
        except ValueError as error:
            raise ValueError('Variable type needs to be int, float, or str'). \
                            with_traceback(error.__traceback__)

        self._stby_cycle = new_cycle

        try:
            self._update_sleep_cycle()
        except ValueError as error:
            raise RuntimeError('Invalid combination of duty cycles,'
                               'need to sum up to 100%'). \
                                with_traceback(error.__traceback__)

    @property
    def sleep_duty_cycle(self):
        return self._sleep_cycle

    @sleep_duty_cycle.setter
    def sleep_duty_cycle(self, _):
        print('Read-only property')

        try:
            self._update_sleep_cycle()
        except ValueError as error:
            raise RuntimeError('Invalid combination of duty cycles,'
                               'need to sum up to 100%'). \
                                with_traceback(error.__traceback__)

    @property
    def standby_current(self):
        return self._stby_cur

    @standby_current.setter
    def standby_current(self, new_standby_current):
        global ureg

        try:
            new_standby_current = ureg.parse_expression(new_standby_current)
        except pint.UndefinedUnitError as error:
            raise ValueError('Invalid unit syntax'). \
                             with_traceback(error.__traceback__)

        if isinstance(new_standby_current, float) or \
           isinstance(new_standby_current, int):
            raise ValueError('No units specified')

        self._stby_cur = new_standby_current

    @property
    def sleep_current(self):
        return self._sleep_cur

    @sleep_current.setter
    def sleep_current(self, new_sleep_current):
        global ureg

        try:
            new_sleep_current = ureg.parse_expression(new_sleep_current)
        except pint.UndefinedUnitError as error:
            raise ValueError('Invalid unit syntax'). \
                             with_traceback(error.__traceback__)

        if isinstance(new_sleep_current, float) or \
           isinstance(new_sleep_current, int):
            raise ValueError('No units specified')

        self._sleep_cur = new_sleep_current

    @property
    def on_current(self):
        return self._on_cur

    @on_current.setter
    def on_current(self, new_on_current):
        global ureg

        try:
            new_on_current = ureg.parse_expression(new_on_current)
        except pint.UndefinedUnitError as error:
            raise ValueError('Invalid unit syntax'). \
                             with_traceback(error.__traceback__)

        if isinstance(new_on_current, float) or \
           isinstance(new_on_current, int):
            raise ValueError('No units specified')

        self._on_cur = new_on_current

    @property
    def voltage(self):
        return self._voltage

    @voltage.setter
    def voltage(self, new_voltage):
        global ureg

        try:
            new_voltage = ureg.parse_expression(new_voltage)
        except pint.UndefinedUnitError as error:
            raise ValueError('Invalid unit syntax'). \
                             with_traceback(error.__traceback__)

        if isinstance(new_voltage, float) or isinstance(new_voltage, int):
            raise ValueError('No units specified')

        self._voltage = new_voltage

    def __repr__(self):
        part_info = "Module {} from vendor {}\n". \
                    format(self.part_number, self.vendor)

        elec_info = ("\tVoltage: {}\n"
                     "\tOn current: {}\n"
                     "\tStandby current: {}\n"
                     "\tSleep current: {}\n"
                     "\tOn duty cycle: {}\n"
                     "\tStandby duty cycle: {}\n"
                     "\tSleep duty cycle: {}\n"
                     "\tTime period: {}\n").format(self._voltage,
                                                   self._on_cur,
                                                   self._stby_cur,
                                                   self._sleep_cur,
                                                   self._on_cycle*100,
                                                   self._stby_cycle*100,
                                                   self._sleep_cycle*100,
                                                   self._period)
        return ''.join([part_info, elec_info])

    def __str__(self):
        part_info = "Module {} from vendor {}\n". \
                    format(self.part_number, self.vendor)

        elec_info = ("\tVoltage: {}\n"
                     "\tOn current: {}\n"
                     "\tStandby current: {}\n"
                     "\tSleep current: {}\n"
                     "\tOn duty cycle: {}\n"
                     "\tStandby duty cycle: {}\n"
                     "\tSleep duty cycle: {}\n"
                     "\tTime period: {}\n").format(self._voltage,
                                                   self._on_cur,
                                                   self._stby_cur,
                                                   self._sleep_cur,
                                                   self._on_cycle*100,
                                                   self._stby_cycle*100,
                                                   self._sleep_cycle*100,
                                                   self._period)
        return ''.join([part_info, elec_info])


class Battery(object):
    """Summary of class here.

    Longer class information....
    Longer class information....

    Attributes:
        likes_spam: A boolean indicating if we like SPAM or not.
        eggs: An integer count of the eggs we have laid.
    """
    required_params = ['electrical_params', 'part_number', 'vendor']

    def __init__(self, subsystem_filename=None, design_margin=None):
        if subsystem_filename is None or design_margin is None:
            raise RuntimeError('Please provide a filename and design margin')

        global ureg

        try:
            with open(subsystem_filename, 'r') as yaml_input_file:
                params = yaml.safe_load(yaml_input_file)
        except IOError as error:
            raise RuntimeError('Error opening file {}, check filename'.
                               format(subsystem_filename)). \
                               with_traceback(error.__traceback__)

        except yaml.YAMLError as error:
            raise RuntimeError('File {} contains invalid YAML syntax'.
                               format(subsystem_filename)). \
                               with_traceback(error.__traceback__)
        else:
            if not all(param in params for param in
                       Battery.required_params):
                raise RuntimeError('Required parameter missing in YAML file')

        self.vendor = params['vendor']
        self.part_number = params['part_number']

        params = params['electrical_params']

        try:
            params['oc_voltage'] = ureg.parse_expression(params['oc_voltage'])
            params['const_current'] = ureg.parse_expression(
                                      params['const_current']
                                      )
            params['pulse_current'] = ureg.parse_expression(
                                      params['pulse_current']
                                      )
            params['capacity'] = ureg.parse_expression(params['capacity'])

            params['derating'] = float(params['derating'])
            design_margin = float(design_margin)
        except pint.UndefinedUnitError as error:
            raise RuntimeError('Check units syntax'). \
                               with_traceback(error.__traceback__)
        except ValueError as error:
            raise RuntimeError('Provide derating and margin as numbers'). \
                               with_traceback(error.__traceback__)

        self._oc_voltage = params['oc_voltage']
        self._const_cur = params['const_current']
        self._pulse_cur = params['pulse_current']
        self._cap = params['capacity']
        self._derating = params['derating'] / 100.0
        self._margin = design_margin / 100.0

        self._par_cells = 1
        self._ser_cells = 1
        self._des_cap = self._cap * (1 - self._derating) * (1 - self._margin)
        self._tot_des_cap = self._des_cap * self._par_cells

    def calc_lifetime(self, energy_consumption, time_unit):
        lifetime = self._tot_des_cap.to_base_units() / \
                   energy_consumption.to_base_units()

        lifetime = lifetime * time_unit

        return lifetime

    def _calc_number_of_cells(self, max_current, avg_current, max_voltage):
        new_par_cells_max_current = int(np.ceil(max_current / self._pulse_cur))
        new_par_cells_avg_current = int(np.ceil(avg_current / self._const_cur))

        self._par_cells = np.max([new_par_cells_avg_current,
                                  new_par_cells_max_current])
        self._ser_cells = int(np.ceil(max_voltage / self._oc_voltage))

        self._tot_des_cap = self._des_cap * self._par_cells

    @property
    def number_cells_total(self):
        return (self._par_cells * self._ser_cells)

    @number_cells_total.setter
    def number_cells_total(self, _):
        print('Read-only property')

    @property
    def number_cells_series(self):
        return self._ser_cells

    @number_cells_series.setter
    def number_cells_series(self, _):
        print('Read-only property')

    @property
    def number_cells_parallel(self):
        return self._par_cells

    @number_cells_parallel.setter
    def number_cells_parallel(self, _):
        print('Read-only property')

    @property
    def design_capacity_total(self):
        return self._tot_des_cap

    @design_capacity_total.setter
    def design_capacity_total(self, _):
        print('Read-only property')

    @property
    def design_capacity_individual(self):
        return self._des_cap

    @design_capacity_individual.setter
    def desgin_capacity_individual(self, _):
        print('Read-only property')

    @property
    def design_margin(self):
        return self._margin

    @design_margin.setter
    def design_margin(self, new_design_margin):
        try:
            new_design_margin = float(new_design_margin)
            new_design_margin /= 100.0
        except ValueError as error:
            raise RuntimeError('Provide margin as number'). \
                               with_traceback(error.__traceback__)

        self._margin = new_design_margin

    @property
    def derating(self):
        return self._derating

    @derating.setter
    def derating(self, new_derating):
        try:
            new_derating = float(new_derating)
            new_derating /= 100.0
        except ValueError as error:
            raise RuntimeError('Provide margin as number'). \
                               with_traceback(error.__traceback__)

        self._derating = new_derating

    @property
    def capacity(self):
        return self._cap

    @capacity.setter
    def capacity(self, new_capacity):
        global ureg

        try:
            new_capacity = ureg.parse_expression(new_capacity)
        except pint.UndefinedUnitError as error:
            raise RuntimeError('Invalid unit syntax'). \
                               with_traceback(error.__traceback__)

        if isinstance(new_capacity, float) or isinstance(new_capacity, int):
            raise ValueError('No units specified')

        self._cap = new_capacity

    @property
    def pulse_current(self):
        return self._pulse_cur

    @pulse_current.setter
    def pulse_current(self, new_pulse_current):
        global ureg

        try:
            new_pulse_current = ureg.parse_expression(new_pulse_current)
        except pint.UndefinedUnitError as error:
            raise RuntimeError('Invalid unit syntax'). \
                               with_traceback(error.__traceback__)

        if isinstance(new_pulse_current, float) or \
           isinstance(new_pulse_current, int):
            raise ValueError('No units specified')

        self._pulse_cur = new_pulse_current

    @property
    def const_current(self):
        return self._const_cur

    @const_current.setter
    def const_current(self, new_const_current):
        global ureg

        try:
            new_const_current = ureg.parse_expression(new_const_current)
        except pint.UndefinedUnitError as error:
            raise RuntimeError('Invalid unit syntax'). \
                               with_traceback(error.__traceback__)

        if isinstance(new_const_current, float) or \
           isinstance(new_const_current, int):
            raise Exception('No units specified')

        self._const_cur = new_const_current

    @property
    def oc_voltage(self):
        return self._oc_voltage

    @oc_voltage.setter
    def oc_voltage(self, new_oc_voltage):
        global ureg

        try:
            new_oc_voltage = ureg.parse_expression(new_oc_voltage)
        except pint.UndefinedUnitError as error:
            raise RuntimeError('Invalid unit syntax'). \
                               with_traceback(error.__traceback__)

        if isinstance(new_oc_voltage, float) or \
           isinstance(new_oc_voltage, int):
            raise ValueError('No units specified')

        self._oc_voltage = new_oc_voltage

    def __repr__(self):
        part_info = "Battery {} from vendor {}\n". \
                    format(self.part_number, self.vendor)

        elec_info = ("\tOpen-circuit Voltage: {}\n"
                     "\tConstant current: {}\n"
                     "\tPulse current: {}\n"
                     "\tBOL capacity: {}\n"
                     "\tDe-rating in %: {}\n").format(self._oc_voltage,
                                                      self._const_cur,
                                                      self._pulse_cur,
                                                      self._cap,
                                                      self._derating*100)
        return ''.join([part_info, elec_info])

    def __str__(self):
        part_info = "Battery {} from vendor {}\n". \
                    format(self.part_number, self.vendor)

        elec_info = ("\tOpen-circuit Voltage: {}\n"
                     "\tConstant current: {}\n"
                     "\tPulse current: {}\n"
                     "\tBOL capacity: {}\n"
                     "\tDe-rating in %: {}\n").format(self._oc_voltage,
                                                      self._const_cur,
                                                      self._pulse_cur,
                                                      self._cap,
                                                      self._derating*100)
        return ''.join([part_info, elec_info])


class Scenario(object):
    """Summary of class here.

    Longer class information....
    Longer class information....

    Attributes:
        likes_spam: A boolean indicating if we like SPAM or not.
        eggs: An integer count of the eggs we have laid.
    """
    pass
