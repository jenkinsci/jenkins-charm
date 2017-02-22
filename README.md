# Overview
[![Build Status](https://travis-ci.org/jenkinsci/jenkins-charm.svg?branch=master)](https://travis-ci.org/jenkinsci/jenkins-charm) [![Coverage Status](https://coveralls.io/repos/github/jenkinsci/jenkins-charm/badge.svg?branch=master)](https://coveralls.io/github/jenkinsci/jenkins-charm?branch=master)

This charm (along with its companion, jenkins-slave) provides an easy way to deploy Jenkins on Ubuntu server and scale out Jenkins slaves.

This charm provides a Jenkins Server which can be accessed, after exposing, on http://<master>:8080.

# Usage

If you want to run jobs on separate nodes you will also need to deploy the jenkins-slave charm:

    juju deploy jenkins
    juju deploy -n 5 jenkins-slave
    juju add-relation jenkins jenkins-slave

The default password for the 'admin' account will be auto-generated.

You can set it using:

    juju set jenkins password=mypassword

Always change it this way - this account is used by the charm to manage slave configuration.

Then feel free to expose your Jenkins master:

    juju expose jenkins

The Jenkins UI will be accessible on http://<master>:8080

## Scale out Usage

The main method to use the Jenkins service at scale is to add units to the jenkins-slave, as illustrated in the example usage:

    juju deploy -n 5 jenkins-slave

Here the "-n 5" is adding 5 additional units (instances) to the jenkins-slave. Of course that "5" can be as large as you wish or you cloud provider supports. Additional information on scaling services with add-unit can be found at [Juju Scaling Docs](https://juju.ubuntu.com/docs/charms-scaling.html).

## Storage Support
This charm includes Juju storage support which can be used in the standard way, for example:

    juju deploy jenkins --storage jenkins=10G

Adding storage to an exising application is not supported.

# Configuration

You have already seen the password configuration in the "Usage" section. Some other interesting config options are plugins and release. You can add config options via the command line with juju set or via a config file. More information on Juju config is at [Juju Config Docs](https://juju.ubuntu.com/docs/charms-config.html).

## Plugin config example

    juju set jenkins plugins=htmlpublisher view-job-filters bazaar git

## Release config example

    juju set jenkins release=trunk

You could also set these config options via a config.yaml on jenkins deploy. For example your config.yaml could look like

    jenkins:
      plugins: htmlpublisher view-job-filters bazaar git
      release: trunk

You would then deploy jenkins with your config such as:

    juju deploy --config config.yaml jenkins

## Extending this charm

If you wish to perform custom configuration of either the master
or slave services, you can branch this charm and add install hooks
into hooks/install.d.

These will be executed when the main install, `config-changed` or
`upgrade-charm` hooks are executed (as the `config-changed` and
`upgrade-charm` hooks just call install)..

Additional hooks are executed in the context of the install hook
so may use any variables which are defined in this hook.

# Backup/Restore Jobs

This charm supports actions that allow you to backup/restore the Jenkins
jobs directory.

* To backup the current jobs directory, run the `backup-jobs` action:

      juju run-action jenkins/0 backup-jobs [artifacts=False] [online=False]

  This will create a gzipped tar archive of the `/var/lib/jenkins/jobs`
  directory. The following action parameters are available:

  * **artifacts**: By default, only the `config.yaml` files for each job are
  included in the archive. If you wish to include all job data, set
  `artifacts=True`.

  * **online**: By default, the action will stop the jenkins service prior to
  backing up the jobs directory. If you wish to backup jobs while jenkins is
  running, set `online=True`.

  Use the UUID from the run-action above to view details about the backup:

      juju show-action-output <action-uuid>

  The output will include a command to retrieve the archive, as well as the
  sha256 sum so you can verify archive integrity.

* To restore an archived jobs directory, first attach the archive as a charm
resource. Currently, this charm supports attaching zip and various flavors of
tar archives (gzipped, bzipped, etc):

      juju attach jenkins jobs=./jobs.tgz

  Once the resource has been attached, run the `restore-jobs` action:

      juju run-action jenkins/0 \
        restore-jobs [online=False] [overwrite=False] [wipe=False]

  This will extract the attached archive into the `/var/lib/jenkins/jobs`
  directory. The following action parameters are available:

  * **online**: By default, the action will stop the jenkins service prior to
  restoring the jobs directory. If you wish to restore jobs while jenkins is
  running, set `online=True`.

    >Note: Jenkins will not see changes to the jobs directory until it reloads
    config from disk. This happens automatically when the service is restarted.
    Running `restore-jobs online=True` will require manual intervention to
    reload the Jenkins jobs.

  * **overwrite**: By default, only restore files that either do not exist or
  are newer than files present in the jobs directory. If you wish to overwrite
  any existing files in the jobs directory, set `overwrite=True`.

    >Note: *overwrite* has no effect when *wipe=True*.

  * **wipe**:  By default, existing data in the jobs directory will be
  kept (though potentially overwritten if the previously mentioned
  *overwrite* option is set to *True*). To remove and recreate an empty jobs
  directory prior to restoration, set `wipe=True`.

  Use the UUID from the run-action above to view details about the restoration:

      juju show-action-output <action-uuid>

  The output will include the name/shasum of the restored archive, as well as
  any error messages that may have occurred during restoration.

# Jenkins Project Information

- [Jenkins Project Website](http://jenkins-ci.org/)
- [Jenkins Bug Tracker](https://wiki.jenkins-ci.org/display/JENKINS/Issue+Tracking)
- [Jenkins mailing lists](http://jenkins-ci.org/content/mailing-lists)
- [Jenkins Plugins](https://wiki.jenkins-ci.org/display/JENKINS/Plugins)
