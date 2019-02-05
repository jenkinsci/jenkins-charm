test:
	tox

lxc-test:
	@$(check-lxc)
	tox

lxc-setup:
	@$(check-lxc)
	sudo apt-get update
	sudo apt-get install -y tox

run-lxc-test:
	./scripts/lxc-test

################################################################################

define check-lxc
    if ! sudo grep -q lxc /proc/1/environ 2> /dev/null; then \
		echo "Not running inside an LXC; aborting."; exit 1; \
	fi
endef
