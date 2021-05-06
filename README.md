# Overview
[![Build Status](https://travis-ci.org/jenkinsci/jenkins-charm.svg?branch=master)](https://travis-ci.org/jenkinsci/jenkins-charm) [![Coverage Status](https://coveralls.io/repos/github/jenkinsci/jenkins-charm/badge.svg?branch=master)](https://coveralls.io/github/jenkinsci/jenkins-charm?branch=master)

This charm (along with its companion, jenkins-slave) provides an easy way to deploy Jenkins on Ubuntu server and scale out Jenkins slaves.

This charm provides a Jenkins Server which can be accessed, after exposing, on `http://<master>:8080`.

# Usage

If you want to run jobs on separate nodes you will also need to deploy the jenkins-slave charm:

    juju deploy jenkins
    juju deploy -n 5 jenkins-slave
    juju add-relation jenkins jenkins-slave

Slaves will attempt to connect via JNLP on port 48484 by default. This is configurable, e.g.:

    juju config jenkins jnlp-port=12345

If you want the previously-default behaviour of a random TCP port, you can set this to -1:

    juju config jenkins jnlp-port=-1

Or if you want to disable the feature entirely, set it to 0:

    juju config jenkins jnlp-port=0

The default password for the 'admin' account will be auto-generated, or can be
set via `juju config`. You can retrieve the auto-generated password using:

    juju run-action jenkins/0 get-admin-credentials

You should avoid changing the admin password within the Jenkins UI - this account is used by the charm to manage slave configuration.

Then feel free to expose your Jenkins master:

    juju expose jenkins

The Jenkins UI will be accessible on `http://<master>:8080`.

## Scale out Usage

The main method to use the Jenkins service at scale is to add units to the jenkins-slave, as illustrated in the example usage:

    juju deploy -n 5 jenkins-slave

Here the "-n 5" is adding 5 additional units (instances) to the jenkins-slave. Of course that "5" can be as large as you wish or your cloud provider supports. Additional information on scaling services with add-unit can be found at [Juju Scaling Docs](https://juju.ubuntu.com/docs/charms-scaling.html).

## Storage Support
This charm includes Juju storage support which can be used in the standard way, for example:

    juju deploy jenkins --storage jenkins=10G

Adding storage to an existing application is not supported.

# Configuration

You have already seen the password configuration in the "Usage" section. Some other interesting config options are plugins and release. You can add config options via the command line with juju set or via a config file. More information on Juju config is at [Juju Config Docs](https://juju.ubuntu.com/docs/charms-config.html).

## Plugin config example

    juju config jenkins plugins=htmlpublisher view-job-filters bazaar git

## Release config example

    juju config jenkins release=trunk

You could also set these config options via a config.yaml on jenkins deploy. For example your config.yaml could look like:

    jenkins:
      plugins: htmlpublisher view-job-filters bazaar git 
      release: trunk 

You would then deploy jenkins with your config such as:

    juju deploy --config config.yaml jenkins
 
## Extending this charm

If you wish to perform custom configuration of either the master or slave services, you can branch this charm and add install hooks into hooks/install.d.

These will be executed when the main install, `config-changed` or `upgrade-charm` hooks are executed (as the `config-changed` and `upgrade-charm` hooks just call install).

Additional hooks are executed in the context of the install hook so you may use any variables which are defined in this hook.

# Jenkins Project Information 

- [Jenkins Project Website](http://jenkins-ci.org/)
- [Jenkins Bug Tracker](https://wiki.jenkins-ci.org/display/JENKINS/Issue+Tracking)
- [Jenkins mailing lists](http://jenkins-ci.org/content/mailing-lists)
- [Jenkins Plugins](https://wiki.jenkins-ci.org/display/JENKINS/Plugins)
