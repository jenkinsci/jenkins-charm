Jenkins Charm for Juju
----------------------

This charm (along with its companion, jenkins-slave) provide an
easy way to deploy Jenkins on Ubuntu server and scale out
jenkins slaves::

   juju deploy jenkins
   juju deploy -n 5 jenkins-slave
   juju add-relation jenkins jenkins-slave

The default password for the 'admin' account will be auto-generated.

You can set it using::

   juju set jenkins password=mypassword

Always change it this way - this account is used by the charm to
manage slave configuration.

Then feel free to expose your jenkins master::

   juju expose jenkins

The jenkins UI will be accessible on http://<master>:8080

Extending this charm
--------------------

If you wish to perform custom configuration of either the master
or slave servers, you can branch this charm and add install hooks
into hooks/install.d.

These will be executed when the main install, config-changed or
upgrade charm hooks are executed.

Additional hooks are executed in the context of the install hook
so may use any variables which are defined in this hook.
