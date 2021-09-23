# Website Deployment

## Setup
If you have not already done so:  
* Clone this repo
* Create and activate a `brain-score.web` conda environment using `environment.yml`
* Make sure `awsebcli` is installed in your environment:  `eb --version` 
    * If not, use `pip install awsebcli`
* Make sure you have AWS credentials in place for AWS account 613927419654
    * If you have multiple profiles and your profile for 613927419654 is not your default, use the `--profile` option in all `eb` commands
* Initialize your `awsebcli` settings with `eb init`
    * When it asks "Select a default region", select "us-east-2 : US East (Ohio)"
    * It should find application "brain-score.web" in account 613927419654 and suggest it;  select that
    * For "Select a keypair" select "Create new KeyPair" (unless you already have a keypair in us-east-2 for account 613927419654)
    * For all other prompts accept the default
* Check that the command line client can see the environments in the account:  `eb list`
    * If the output does not include `brain-score-web-dev` and `brain-score-web-prod`, default region or AWS credentials may be misconfigured

## To Deploy
* If there are changes to django models, make sure makemigrations has been run and the migration checked into git
* Deploy the latest Git commit to the development environment:  `eb deploy brain-score-web-dev  --timeout 20`
    * This can take around 15 minutes
* If there are database migrations, apply them from within the container:  
    * `eb ssh brain-score-web-dev`
        * Reply "yes" to the fingerprint question
        * You should get an EC2 instance prompt like `[ec2-user@ip-172-31-32-98 ~]$`
    * `sudo docker ps`
        * This should produce information about the Docker container running on this host
        * Note the container name;  it will likely be something like "fervent_edison"
    * `sudo docker exec -it fervent_edison /bin/bash`
        * You should get a Docker container prompt like `(brain-score.web) root@64a27216fa70:/app#`
    * `python manage.py migrate`
        * This should produce output from Django making changes to the database schema
    * Exit the container:  `exit`
    * Exit the EC2 host:  `exit`
* Check the dev website:  http://brain-score-web-dev.us-east-2.elasticbeanstalk.com/
* If the dev website passes tests, deploy to production:  `eb deploy brain-score-web-prod  --timeout 20`
* If necessary repeat migrations, but this time begin with `eb ssh brain-score-web-prod`

## To Create Elastic Beanstalk Environments
If the Elastic Beanstalk environments do not exist or need to be recreated:  

```
eb create brain-score-web-dev -c brain-score-web-dev -r us-east-2 -p Docker --envvars DEBUG=True,DOMAIN=localhost:brain-score-web-dev.us-east-2.elasticbeanstalk.com,DB_CRED=brainscore-1-ohio-cred
```

```
eb create brain-score-web-prod -c brain-score-web-prod -r us-east-2 -p Docker --envvars DEBUG=False,DOMAIN=localhost:brain-score-web-prod.us-east-2.elasticbeanstalk.com:www.brain-score.org,DB_CRED=brainscore-prod-ohio-cred
```

### Retrieving the django log

First, install the Elastic Beanstalk command line interface: `pip install awsebcli`

Initialize in the `brain-score.web` directory with `eb init`:
```
(brain-score.web) jjpr-mit:brain-score.web jjpr$ eb init


Select a default region
[...]
14) us-east-2 : US East (Ohio)
[...]
(default is 3): 14


Select an application to use
1) brain-score.web
2) [ Create new Application ]
(default is 1):


It appears you are using Docker. Is this correct?
(Y/n): y
Do you wish to continue with CodeCommit? (y/N) (default is n): n

Do you want to set up SSH for your instances?
(Y/n): y


Select a keypair.
1) jjpr
2) [ Create new KeyPair ]
(default is 1): 1
```

Finally, run `eb logs -a brain-score-web-prod` to store the logs locally. You can find them in e.g. `.elasticbeanstalk/logs/latest/i-08c7dffdb408ff6d8/var/log/eb-docker/containers/eb-current-app/eb-102014d535e7-stdouterr.log` (You might have to manually figure out the path hashes on your end).
