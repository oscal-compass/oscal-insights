# -*- mode:python; coding:utf-8 -*-
# Copyright (c) 2024 IBM Corp. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""OSCAL component-definition insights."""

import argparse
import logging
import pathlib
import sys
from functools import cmp_to_key
from typing import Dict, List

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from trestle.core.catalog.catalog_interface import CatalogInterface
from trestle.core.profile_resolver import ProfileResolver
from trestle.oscal.catalog import Catalog
from trestle.oscal.common import Property
from trestle.oscal.component import ComponentDefinition
from trestle.oscal.component import DefinedComponent

log_level = logging.INFO
log_format = logging.Formatter('%(asctime)s %(levelname).1s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)
logger.setLevel(log_level)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
handler.setFormatter(log_format)
logger.addHandler(handler)

recurse = True


class Utilities():
    """Utilities."""

    @staticmethod
    def compare_controls(c0: str, c1: str) -> int:
        """Compare controls."""
        if '-' not in c0 or '-' not in c1:
            if c0 > c1:
                return 1
            if c0 < c1:
                return -1
            return 0
        c0_lhs = c0.split('-')[0]
        c0_rhs = c0.split('-')[1]
        c1_lhs = c1.split('-')[0]
        c1_rhs = c1.split('-')[1]
        if c0_lhs > c1_lhs:
            return 1
        if c0_lhs < c1_lhs:
            return -1
        f0 = float(c0_rhs)
        f1 = float(c1_rhs)
        if f0 > f1:
            return 1
        if f0 < f1:
            return -1
        return 0


class CatalogInsights():
    """Catalog Insights."""

    def __init__(self, _base: str, _file: str) -> None:
        """Initialize."""
        self._base = _base
        self._file = _file
        if not self._is_catalog():
            self._catalog = ProfileResolver.get_resolved_profile_catalog(
                pathlib.Path(self._base),
                self._file,
            )
        else:
            _path = pathlib.Path(self._base) / self._file
            self._catalog = Catalog.oscal_read(_path)
        self.catalog_interface = CatalogInterface(self._catalog)
        #
        self._analyze()

    def _is_catalog(self) -> bool:
        """Is catalog test."""
        rval = True
        try:
            _path = pathlib.Path(self._base) / self._file
            Catalog.oscal_read(_path)
        except Exception:
            rval = False
        return rval

    def _analyze(self) -> None:
        """Analyze."""
        ctl_list = []
        for control in self.catalog_interface.get_all_controls_from_catalog(recurse):
            ctl_list.append(control.id)
        self._control_id_list = list(set(ctl_list))

    def get_controls_count(self):
        """Get controls count."""
        return len(self._control_id_list)


class ComponentDefinitionInsights():
    """Component Definition Insights."""

    def __init__(self, _base: str, _file: str) -> None:
        """Initialize."""
        self._base = _base
        self._file = _file
        self._path = pathlib.Path(self._base) / self._file
        self._component_definition = ComponentDefinition.oscal_read(self._path)
        #
        self._map_component_to_control = {}
        self._map_control_to_component = {}
        self._map_component_and_control_to_rule = {}
        self._map_validation_rule_to_implementation = {}
        #
        self._map_component_to_rules_to_checks = {}
        self._list_validation_rules = []
        self._list_validation_checks = []
        #
        self._catalogs = {}
        #
        self._analyze()

    def _analyze(self) -> None:
        """Analyze."""
        for component in self._component_definition.components:
            if component.type != 'Validation':
                self.analyze_component(component)
        for component in self._component_definition.components:
            if component.type == 'Validation':
                self.analyze_component_validation(component)

    def analyze_component_validation(self, component: ComponentDefinition) -> None:
        """Analyze component of type Validation."""
        if not component.props:
            return
        rule_set_ids = []
        if component.title not in self._map_component_to_rules_to_checks:
            self._map_component_to_rules_to_checks[component.title] = {}
        for prop in component.props:
            if prop.remarks in rule_set_ids:
                continue
            rule_set_ids.append(prop.remarks)
        for rule_set_id in rule_set_ids:
            rule = self._get_prop(component.props, rule_set_id, 'Rule_Id')
            if rule:
                implemented = self._get_prop(component.props, rule_set_id, 'Rule_Data_Model_Fact_Type_Id_List')
                self._map_validation_rule_to_implementation[rule] = implemented
                check = self._get_prop(component.props, rule_set_id, 'Check_Id')
                if check:
                    self._list_validation_rules.append(rule)
                    self._list_validation_checks.append(check)
                    self._map_component_to_rules_to_checks[component.title][rule] = check

    def analyze_component(self, component: ComponentDefinition) -> None:
        """Analyze component of type not Validation."""
        self._map_component_to_control[component.title] = self.get_component_controls(component)
        # control-to-components
        for control in self._map_component_to_control[component.title]:
            if control not in self._map_control_to_component:
                self._map_control_to_component[control] = []
            if component.title not in self._map_control_to_component[control]:
                self._map_control_to_component[control].append(component.title)
        self.analyze_rules(component)
        self.analyze_catalogs(component)

    def analyze_rules(self, component: ComponentDefinition) -> None:
        """Analyze rules."""
        for ci in component.control_implementations:
            for ir in ci.implemented_requirements:
                rules = self.get_rules(ir.props)
                if not rules:
                    continue
                if component.title not in self._map_component_and_control_to_rule:
                    self._map_component_and_control_to_rule[component.title] = {}
                if ir.control_id not in self._map_component_and_control_to_rule[component.title]:
                    self._map_component_and_control_to_rule[component.title][ir.control_id] = []
                value = self._map_component_and_control_to_rule[component.title][ir.control_id] + rules
                self._map_component_and_control_to_rule[component.title][ir.control_id] = list(set(value))

    def analyze_catalogs(self, component: ComponentDefinition) -> None:
        """Analyze catalogs."""
        for ci in component.control_implementations:
            if not ci.source:
                continue
            if ci.source not in self._catalogs:
                self._catalogs[ci.source] = CatalogInsights(self._base, ci.source)

    def _get_prop(self, props: List[Property], rule_set_id: str, prop_name: str) -> str:
        """Get prop from rule set."""
        rval = None
        for prop in props:
            if prop.remarks != rule_set_id:
                continue
            if prop.name == prop_name:
                rval = prop.value
                break
        return rval

    def get_check_for_rule(self, rule: str) -> str:
        """Get check for rule."""
        rval = None
        for component_id in self._map_component_to_rules_to_checks:
            if rule in self._map_component_to_rules_to_checks[component_id].keys():
                rval = self._map_component_to_rules_to_checks[component_id][rule]
                break
        return rval

    def get_catalogs_controls_count(self) -> int:
        """Get catalogs controls count."""
        count = 0
        for key in self._catalogs.keys():
            catalog_insights = self._catalogs[key]
            count += catalog_insights.get_controls_count()
        return count

    def get_catalogs(self) -> List[str]:
        """Get catalogs."""
        return self._catalogs

    def get_validation_rules(self):
        """Get list of validation rules."""
        return self._list_validation_rules

    def get_validation_checks(self):
        """Get list of validation checks."""
        return self._list_validation_checks

    def get_rules(self, props: List[Property]) -> List[str]:
        """Get rules."""
        rval = []
        if props:
            for prop in props:
                if prop.name == 'Rule_Id':
                    rval.append(prop.value)
        return rval

    def get_component_controls(self, component: DefinedComponent) -> List[str]:
        """Get components controls."""
        rval = []
        for ci in component.control_implementations:
            for ir in ci.implemented_requirements:
                control_id = ir.control_id
                if control_id not in rval:
                    rval.append(control_id)
        return rval

    def get_version(self) -> str:
        """Get version."""
        return self._component_definition.metadata.version

    def get_last_modified(self) -> str:
        """Get last modified."""
        return self._component_definition.metadata.last_modified

    def get_reduced_title(self) -> str:
        """Get reduced title."""
        return self._component_definition.metadata.title.split()[-1]

    def get_all_controls_sorted(self) -> List[str]:
        """Get all controls sorted."""
        return sorted(self._map_control_to_component.keys(), key=cmp_to_key(Utilities.compare_controls))

    def get_all_components_sorted(self) -> List[str]:
        """Get all components sorted."""
        return sorted(self._map_component_to_control.keys())

    def get_map_component_to_control(self) -> Dict[str, List[str]]:
        """Get map of components to controls."""
        return self._map_component_to_control

    def get_map_control_to_component(self) -> Dict[str, List[str]]:
        """Get map of controls title to components."""
        return self._map_control_to_component

    def get_map_component_to_control_check_coverage(self) -> Dict[str, List[float]]:
        """Get map of components to controls check coverage."""
        rval = {}
        for component in self._map_component_and_control_to_rule.keys():
            pct = 0
            if component in self.get_all_components_sorted():
                controls_to_rules = self._map_component_and_control_to_rule[component]
                count_rules = 0
                count_checks = 0
                controls = controls_to_rules.keys()
                for control in controls:
                    rules = controls_to_rules[control]
                    for rule in rules:
                        count_rules += 1
                        check = self.get_check_for_rule(rule)
                        if check:
                            count_checks += 1
                pct = count_checks / count_rules * 100
            rval[component] = pct
        return rval

    def get_map_validation_rule_to_implementation(self) -> Dict[str, str]:
        """Get map of components to controls check coverage."""
        return self._map_validation_rule_to_implementation


label_number_of_components = 'Number of Components'
color_good = 'mediumseagreen'
color_other = 'silver'
color_warn = 'gold'


class OscalComponentDefinitionInsights():
    """Oscal Component Definition Insights."""

    def set_name(self, _name: str) -> None:
        """Set name."""
        self._name = _name

    def get_label_controls(self):
        """Get label controls."""
        return f'{self._name} Controls'

    def get_label_number_of_controls(self):
        """Get label number of controls."""
        return f'Number of {self.get_label_controls()}'

    def get_label_part_covered(self):
        """Get label part covered."""
        return '\nCovered'

    def get_label_part_not_covered(self):
        """Get label part covered."""
        return '\nNot Covered'

    def get_label_part_implemenation_exists(self):
        """Get label implementation exists."""
        return 'Implementation\nExists'

    def get_label_part_implementation_missing(self):
        """Get label implementation missing."""
        return 'Implementation\nMissing'

    def scale(self, dim: float, div: int, maxv: int) -> float:
        """Scale dimensional value."""
        if maxv > div:
            return (dim / div) * maxv
        return dim

    def run(self) -> None:
        """Run."""
        # parse args
        args = self.parse_args()
        # analyze component-definition
        self.cdi = ComponentDefinitionInsights(args.base_path, args.file_path)
        # prep for plots
        self.set_name(self.cdi.get_reduced_title())
        # plots
        self.make_plots(args)

    def get_ticks(self, x_pos: List[int]) -> int:
        """Get ticks."""
        rval = 1
        ticks = int(len(x_pos) / 10)
        if ticks > 1:
            rval = ticks
        return rval

    def make_plot_01(self, args: Dict) -> None:
        """Make plot 01."""
        count_controls_covered = len(self.cdi.get_all_controls_sorted())
        count_controls = self.cdi.get_catalogs_controls_count() - count_controls_covered
        colors = [f'{color_good}', f'{color_other}']
        wedgeprops = {'edgecolor': 'black', 'linewidth': 2, 'antialiased': True}
        label01 = f'{self.get_label_controls()} {self.get_label_part_covered()} {count_controls_covered}'
        label02 = f'{self.get_label_controls()} {self.get_label_part_not_covered()} {count_controls}'
        labels = label01, label02
        counts = [count_controls_covered, count_controls]
        fig, ax = plt.subplots()
        fig.patch.set_facecolor('wheat')
        ax.pie(counts, labels=labels, colors=colors, wedgeprops=wedgeprops, autopct='%1.0f%%')
        output_file = pathlib.Path(args.output_path) / 'controls-coverage.png'
        plt.savefig(f'{output_file}', dpi=400)

    def make_plot_02(self, args: Dict) -> None:
        """Make plot 02."""
        _map = self.cdi.get_map_control_to_component()
        keys = self.cdi.get_all_controls_sorted()
        max_x = 0
        max_y = 0
        y_pos = []
        x_pos = []
        for key in keys:
            max_y += 1
            y_pos.append(key)
            x_val = len(_map[key])
            if x_val > max_x:
                max_x = x_val
            x_pos.append(x_val)
        w = self.scale(6.4, 30, max_x)
        h = self.scale(4.8, 30, max_y)
        fig, ax = plt.subplots(figsize=(w, h))
        fig.patch.set_facecolor('wheat')
        t1 = f'version: {self.cdi.get_version()}'
        t2 = f'last modified date: {self.cdi.get_last_modified().date()}'
        plt.title(f'{t1}', fontsize=10, loc='left')
        plt.title(f'{t2}', fontsize=10, loc='right')
        ax.barh(y_pos, x_pos, align='center')
        ax.invert_yaxis()  # labels read top-to-bottom
        count_controls = len(keys)
        count_controls_catalog = self.cdi.get_catalogs_controls_count()
        ax.set_xlabel(f'{label_number_of_components}')
        ax.set_ylabel(f'{self.get_label_controls()}: {count_controls} covered of {count_controls_catalog} in catalog')
        ax.set_yticklabels(y_pos, fontsize=8)
        plt.tight_layout()
        ticks = self.get_ticks(x_pos)
        plt.gca().xaxis.set_major_locator(mticker.MultipleLocator(ticks))
        output_file = pathlib.Path(args.output_path) / 'controls-to-number-of-components.png'
        plt.savefig(f'{output_file}', dpi=400)

    def make_plot_03(self, args: Dict) -> (int, int):
        """Make plot 03."""
        _map = self.cdi.get_map_component_to_control()
        keys = _map.keys()
        max_x = 0
        max_y = 0
        y_pos = []
        x_pos = []
        for key in keys:
            max_y += 1
            y_pos.append(key)
            x_val = len(_map[key])
            if x_val > max_x:
                max_x = x_val
            x_pos.append(x_val)
        w = self.scale(6.4, 30, max_x)
        h = self.scale(4.8, 30, max_y)
        fig, ax = plt.subplots(figsize=(w, h))
        fig.patch.set_facecolor('powderblue')
        t1 = f'version: {self.cdi.get_version()}'
        t2 = f'last modified date: {self.cdi.get_last_modified().date()}'
        plt.title(f'{t1}', fontsize=10, loc='left')
        plt.title(f'{t2}', fontsize=10, loc='right')
        ax.barh(y_pos, x_pos, align='center')
        ax.invert_yaxis()  # labels read top-to-bottom
        count_components = len(keys)
        ax.set_xlabel(f'{self.get_label_number_of_controls()}')
        ax.set_ylabel(f'Components: {count_components}')
        ax.set_yticklabels(y_pos, fontsize=8)
        plt.tight_layout()
        if len(x_pos) > 20:
            ticks = 2
        else:
            ticks = 1
        plt.gca().xaxis.set_major_locator(mticker.MultipleLocator(ticks))
        output_file = pathlib.Path(args.output_path) / 'components-to-number-of-controls.png'
        plt.savefig(f'{output_file}', dpi=400)
        return (w, h)

    def make_plot_04(self, args: Dict, w: int, h: int) -> None:
        """Make plot 04."""
        _map = self.cdi.get_map_component_to_control_check_coverage()
        keys = _map.keys()
        y_pos = []
        x_pos = []
        color = []
        for key in keys:
            y_pos.append(key)
            x_val = _map[key]
            if x_val < 100:
                color.append(f'{color_warn}')
            else:
                color.append(f'{color_good}')
            x_pos.append(x_val)
        fig, ax = plt.subplots(figsize=(w, h))
        fig.patch.set_facecolor('powderblue')
        t1 = f'version: {self.cdi.get_version()}'
        t2 = f'last modified date: {self.cdi.get_last_modified().date()}'
        plt.title(f'{t1}', fontsize=10, loc='left')
        plt.title(f'{t2}', fontsize=10, loc='right')
        ax.barh(y_pos, x_pos, align='center', color=color)
        ax.invert_yaxis()  # labels read top-to-bottom
        count_components = len(keys)
        ax.set_xlabel(f'Percentage of {self.get_label_controls()} with assessment checks')
        ax.set_ylabel(f'Components: {count_components}')
        ax.set_yticklabels(y_pos, fontsize=8)
        plt.tight_layout()
        output_file = pathlib.Path(args.output_path) / 'components-to-percentage-of-controls-covered-checks.png'
        plt.savefig(f'{output_file}', dpi=400)

    def make_plot_05(self, args: Dict) -> None:
        """Make plot 05."""
        v_rules = self.cdi.get_validation_rules()
        v_rule_count_unique = len(set(v_rules))
        v_checks = self.cdi.get_validation_checks()
        v_check_count = len(v_checks)
        v_check_count_unique = len(set(v_checks))
        v_check_count_reused = v_check_count - v_check_count_unique
        y_pos = ['Rules', 'Assessment Checks (unique)', 'Assessment Checks (re-used)']
        x_pos = [v_rule_count_unique, v_check_count_unique, v_check_count_reused]
        w = 6.4
        h = 4.8
        fig, ax = plt.subplots(figsize=(w, h))
        fig.patch.set_facecolor('thistle')
        t1 = f'version: {self.cdi.get_version()}'
        t2 = f'last modified date: {self.cdi.get_last_modified().date()}'
        plt.title(f'{t1}', fontsize=10, loc='left')
        plt.title(f'{t2}', fontsize=10, loc='right')
        hbars = ax.barh(y_pos, x_pos, align='center')
        ax.invert_yaxis()  # labels read top-to-bottom
        ax.set_xlabel('Count')
        ax.set_yticklabels(y_pos, fontsize=8)
        plt.tight_layout()
        upper_limit = (max(x_pos) + 50) // 100 * 100 + 100
        ax.bar_label(hbars)
        ax.set_xlim(0, upper_limit)  # adjust xlim to fit labels
        output_file = pathlib.Path(args.output_path) / 'rules-checks-counts.png'
        plt.savefig(f'{output_file}', dpi=400)

    def make_plot_06(self, args: Dict) -> None:
        """Make plot 06."""
        v_rules_map = self.cdi.get_map_validation_rule_to_implementation()
        count_implementation_exists = 0
        count_rules = len(v_rules_map)
        for key in v_rules_map.keys():
            if v_rules_map[key]:
                count_implementation_exists += 1
        count_implementation_missing = count_rules - count_implementation_exists
        wedgeprops = {'edgecolor': 'black', 'linewidth': 2, 'antialiased': True}
        label01 = f'{self.get_label_part_implemenation_exists()}'
        label02 = f'{self.get_label_part_implementation_missing()}'
        if count_implementation_exists and count_implementation_missing:
            labels = [label01, label02]
            counts = [count_implementation_exists, count_implementation_missing]
            colors = [f'{color_good}', f'{color_other}']
        elif count_implementation_exists:
            labels = [label01]
            counts = [count_implementation_exists]
            colors = [f'{color_good}']
        else:
            labels = [label02]
            counts = [count_implementation_missing]
            colors = [f'{color_other}']
        fig, ax = plt.subplots()
        fig.patch.set_facecolor('wheat')
        ax.pie(counts, labels=labels, colors=colors, wedgeprops=wedgeprops, autopct='%1.0f%%')
        output_file = pathlib.Path(args.output_path) / 'implemenations-exist.png'
        plt.savefig(f'{output_file}', dpi=400)

    def make_plots(self, args: Dict):
        """Make plots."""
        pathlib.Path(args.output_path).mkdir(parents=True, exist_ok=True)
        # 1 - controls-coverage
        self.make_plot_01(args)
        # 2 - controls-to-number-of-components
        self.make_plot_02(args)
        # 3 - components-to-number-of-controls
        w, h = self.make_plot_03(args)
        # 4 - components-to-percentage-of-controls-covered-checks
        self.make_plot_04(args, w, h)
        # 5 - rules & checks counts
        self.make_plot_05(args)
        # 6 - implementation status
        self.make_plot_06(args)

    def parse_args(self) -> Dict:
        """Parse args."""
        description = 'Oscal Component Definition Insights'
        epilog = 'Provide OSCAL component-definition insights.'
        parser = argparse.ArgumentParser(description=description, epilog=epilog)
        required = parser.add_argument_group('required arguments')
        help_base_path = 'base path to trestle workspace'
        required.add_argument('--base-path', action='store', required=True, help=help_base_path)
        help_file_path = 'file path to trestle workspace component-defintion.json'
        required.add_argument('--file-path', action='store', required=True, help=help_file_path)
        help_output_path = 'output path to folder to contain produced results'
        required.add_argument('--output-path', action='store', required=True, help=help_output_path)
        return parser.parse_args()


def main():
    """Mainline."""
    opi = OscalComponentDefinitionInsights()
    opi.run()


if __name__ == '__main__':
    main()
