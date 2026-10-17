# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
    config.vm.box = "alvistack/ubuntu-24.04"
    config.vm.provider  :virtualbox do |v|
        v.memory = 1024
        v.linked_clone = true
    end

    config.vm.define "muserv" do |app|
        app.vm.hostname = "home.mikkel.cc.test"
        app.vm.network "private_network", ip: "192.168.56.4"
    end
    config.vm.provision "ansible" do |ansible|
        ansible.verbose = "v"
        ansible.playbook = "deploy.yml"
    end
end
