require 'pathname'
require 'tempfile'
require 'yaml'

srvpath = Pathname.new(File.dirname(__FILE__)).realpath
configfile = YAML.load_file(File.join(srvpath, "/.gitlab-ci.yml"))
# use the first URL for the remote called 'origin'
remote_url = `git remote -v`.gsub(/.*\sorigin\s+(https:\S*).*/m, '\1').strip

# set up essential environment variables
env = configfile['variables']
env['CI_PROJECT_DIR'] = '/builds/fdroid/repomaker'
env_file = Tempfile.new('env')
File.chmod(0644, env_file.path)
env.each do |k,v|
    env_file.write("export #{k}='#{v}'\n")
end
env_file.rewind

sourcepath = '/etc/profile.d/env.sh'
header = "#!/bin/bash -ex\nsource #{sourcepath}\ncd $CI_PROJECT_DIR\n"

before_script_file = Tempfile.new('before_script')
File.chmod(0755, before_script_file.path)
before_script_file.write(header)
configfile['units']['before_script'].flatten.each do |line|
    before_script_file.write(line)
    before_script_file.write("\n")
end
before_script_file.rewind

Vagrant.configure("2") do |config|
  config.vm.box = "debian/bullseye64"
  config.vm.network "forwarded_port", guest: 8000, host: 8000
  config.vm.synced_folder '.', '/vagrant', disabled: true
  config.vm.provision "file", source: env_file.path, destination: 'env.sh'
  config.vm.provision :shell, inline: <<-SHELL
    set -ex

    apt-get update
    apt-get -qy install git

    mv ~vagrant/env.sh #{sourcepath}
    source #{sourcepath}
    mkdir -p $(dirname $CI_PROJECT_DIR)
    chown -R vagrant.vagrant $(dirname $CI_PROJECT_DIR)
    git clone #{remote_url} $CI_PROJECT_DIR
    chmod -R a+rX,u+w $CI_PROJECT_DIR
    chown -R vagrant.vagrant $CI_PROJECT_DIR
SHELL
  config.vm.provision "file", source: before_script_file.path, destination: 'before_script.sh'
  config.vm.provision :shell, inline: '/home/vagrant/before_script.sh'
  config.vm.provision :shell, inline: 'chown -R vagrant.vagrant $CI_PROJECT_DIR'

  # remove this block or comment it out to use VirtualBox instead of libvirt
  config.vm.provider :libvirt do |libvirt|
    libvirt.memory = 512
  end
end
