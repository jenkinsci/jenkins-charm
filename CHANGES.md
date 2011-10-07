jenkins 15
----------

* [james-page] Refactoring to use private address as and where required.

jenkins 14
----------

* [james-page] Added release option to support using upstream archives as source of 
  software - distro (ubuntu), lts (jenkins), trunk(jenkins)
* [james-page] Added username and password configuration parameters to secure jenkins
  master instance on first boot - can be reconfigured post install as well
* [james-page] renamed upgrade-formula to upgrade-charm and added config-changed as 
  call to install

jenkins 13
----------

* [james-page] Migrated ensemble-log calls to juju-log inline with project renaming
* [james-page] Fixed up use of ENSEMBLE_REMOTE_UNIT -> JUJU_REMOTE_UNIT for slave names
* [kaaloo] Fixup str -> string in config.yaml
