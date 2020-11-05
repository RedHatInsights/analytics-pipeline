# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|

  config.vm.box = "generic/ubuntu2004"

  config.vm.provider :libvirt do |libvirt|
    libvirt.cpus = 4
    libvirt.memory = 8000
  end

  config.vm.synced_folder ".", "/vagrant", type: "nfs", nfs_udp: false, :linux__nfs_options => ["async,rw,no_subtree_check,no_root_squash"]

  config.vm.provision "shell", inline: <<-SHELL
    apt-get update
    #apt upgrade
    apt install -y python3
    apt install -y python3-pip
    python3 -m pip install ansible
  SHELL

  config.vm.provision "ansible_local" do |ansible|
    ansible.verbose = true
    ansible.playbook = "playbooks/vagrant.yml"
    ansible.galaxy_role_file = "playbooks/vagrant.requirements.yml"
  end

end
