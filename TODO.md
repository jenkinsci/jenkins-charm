TODO
====

* Updates from jenkins slaves for labels - would be handy to be able to change
  on the fly - not supported by python-jenkins yet.
* [james-page] Source configuration: distro, trunk, lts
  - Default is distro - good for oneiric and natty but not earlier and pinned
    to version in distro.
  - trunk: use upstream Jenkins archive and get the most recent bleeding 
    edge Jenkins .deb instead.
  - lts: use upstream Jenkins archive for LTS support releases (every 6 months
    compromise between distro and trunk!
* [james-page] Configure an default username and password so that the install is protected
  from install onwards
