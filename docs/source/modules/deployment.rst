.. _website-deployment:

Website Deployment
##################

AWS and Elastic Beanstalk
*************************

1. The website is hosted on AWS via Elastic Beanstalk (EB) running on EC2 instances. There is both a dev and a prod site,
   and ideally, dev will always be a copy of prod (for website staging, see below).
2. There are currently 4 EB instances visible when viewing the AWS Console (note: AWS calls the website the "console",
   and this is different from the "console" CLI):

   * The web console can be accessed `here <https://us-east-2.console.aws.amazon.com/elasticbeanstalk/home?region=us-east-2#/environments>`_,
     assuming you have credentials for Brain-Score's AWS. If you do not have creds, ask a Brain-Score team member to create some for you.
   * The environments in use are the ones that contain the substring ``updated``. The other 2 are legacy environments
     that are no longer active and can probably be removed in the future.
3. When viewing this link above for the web console, the dev site might show a ``Severe`` health status—this is OK and
   can be safely ignored. It has to do with Django not getting along well with EB's Load Balancer. See (6) for more
   about the Load Balancer.
4. Prod's status should always be green ``Ok``. If it is not, then something is broken. To troubleshoot, click on the
   prod instance and look at the events immediately below its information on the next page:

   * To Troubleshoot an instance that has non-``Ok`` status, you can either view the Health tab or ``Logs`` tab to get the logs.
   * You can either download the last 100 lines of logs or the full logs. *This is what you will want to do to see exactly
     what error broke the website, usually a Django or Python error*.
   * If you download the logs, there will be a bunch of files in that zip. You are looking for a file called
     ``eb-<some number hash>-stderr.log``, located in ``eb-docker/containers/eb-current-app`` folder.
   * If you are troubleshooting, you can IGNORE the error (if you see it) that looks like this:
     ``django.core.exceptions.DisallowedHost: Invalid HTTP_HOST header: '<SOME IP ADDRESS>'. You may need to add
     '<SOME IP ADDRESS>' to ALLOWED_HOSTS.`` This error causes the same issue that makes dev appear as ``Severe``, and
     deals with EB's Internal Load Balancer not playing nice with Django.
   * Most of the time, a quick ``CMD-f`` for the server 500 error will show you exactly what went wrong.
5. In the instance's console view, you can also explore other things, such as the site monitoring metrics as well.
6. AWS's EB Load Balancer works in conjunction with Auto Scaling. This means that the Load Balancer triggers an auto-scaling
   event, which can create up to 4 instances to run in parallel. We can change that max if need be.

   * The Scaling Event is triggered by instance CPU utilization. If the CPU utilization is above 25%, then a new instance will be launched, up to 4 times.
   * In order to change this (if things need to be modified in the future), you can go into the instance itself and modify the triggers for auto-scaling events.
7. AWS HELP Tips/Tricks: If the site goes down, and you do not know how to fix it, contact AWS via the web portal:

   * Top right of AWS website -> click on question mark in circle icon -> ``Support Center``
   * All the way to the right, in an orange box, click ``Create Case``
   * Choose ``Technical`` and then click ``Next Step: Additional Information``
   * Choose ``Elastic Beanstalk`` for the ``Service`` dropdown, and use your best judgment for the ``Category`` Dropdown.
     Usually, in the past, Mike has chosen either ``Environment Issue`` or ``Application Deployment Issue``.
   * Choose ``Production System Down`` for the ``Severity`` dropdown.
   * Fill in the ``Subject`` and ``Description`` fields, and attach any logs that you want (optional).
   * For the three fields at the bottom: ``Application Name`` is ``brain-score.web``, ``Environment Name`` is the instance
     itself (the one containing ``updated``), and ``Region`` is ``US-14-East``. Then click ``Next Step: Solve now or contact us``
     at the bottom right in orange to move on to the next page.
   * Finally, click the ``Contact us`` icon in the middle of the page to open the corresponding tab, and select ``Chat``
     as the contact method. **IMPORTANT**: Add your email/whoever else needs to be looped in into the ``Additional Contacts``
     field, as the default right now is Chris Shay, and if you do not add your email, you will not see their response (if you use the ``Web`` Option!).
   * When you are chatting with them, it is easiest to simply ask the person to meet over a Chime call if they do not offer first!

Website Staging Flow/Operations (Via Command Line/PR)
*****************************************************

1. Test any changes on LocalHost to make sure they appear and function correctly.
2. Open a PR with your changes on Brain-Score.web's GitHub.
3. Once PR tests pass, deploy to Dev: ``eb deploy Brain-score-web-dev-updated``.
4. Test out changes on Dev: i.e., make sure everything looks good on dev using the dev `website <https://brain-score-web-dev-updated.kmk2mcntkw.us-east-2.elasticbeanstalk.com>`_.

   * The Dev site and LocalHost DO NOT use HTTPS, only HTTP. Do not get spooked if you get weird CSRF errors.
5. If Dev looks good, then merge PR into master upon approval.
6. Once PR is merged, create a new branch from master locally, fetch (pull) changes, and deploy to prod with this command: ``eb deploy Brain-score-web-prod-updated``.
7. Once the Prod site looks good, visit the leaderboard on both vision and language at least once, in order to populate the server-side cache.

Deployment Account Setup
************************

If you have not already done so:

1. Clone this repo
2. Create and activate a ``brain-score.web`` conda environment using ``environment.yml``.
3. Make sure ``awsebcli`` is installed in your environment:  ``eb --version``.

   * If not, use ``pip install awsebcli``.
4. Make sure you have AWS credentials in place for AWS account 613927419654.

   * If you have multiple profiles and your profile for 613927419654 is not your default, use the ``--profile`` option in all ``eb`` commands.
5. Initialize your ``awsebcli`` settings with ``eb init``.

   * When it asks "Select a default region", select "us-east-2 : US East (Ohio)".
   * It should find application "brain-score.web" in account 613927419654 and suggest it; select that.
   * For "Select a keypair" select "Create new KeyPair" (unless you already have a keypair in us-east-2 for account 613927419654).
   * For all other prompts accept the default.
6. Check that the command line client can see the environments in the account:  ``eb list``.

   * If the output does not include ``brain-score-web-dev`` and ``brain-score-web-prod``, default region or AWS credentials may be misconfigured.

To Deploy (if migrations are made)
**********************************

1. If there are changes to Django models, make sure make migrations has been run and the migration checked into git.

2. Deploy the latest Git commit to the development environment:  ``eb deploy brain-score-web-dev-updated --timeout 20``.

   * This can take around 15 minutes.
3. If there are database migrations, apply them from within the container:

   * ``eb ssh brain-score-web-dev-updated``

      * Reply "yes" to the fingerprint question.
      * You should get an EC2 instance prompt like ``[ec2-user@ip-172-31-32-98 ~]$``.

   * ``sudo docker ps``

      * This should produce information about the Docker container running on this host.
      * Note the container name; it will likely be something like "fervent_edison".

   * ``sudo docker exec -it fervent_edison /bin/bash``

      * You should get a Docker container prompt like ``(brain-score.web) root@64a27216fa70:/app#``.

   * ``python manage.py migrate``

      * This should produce output from Django making changes to the database schema.

   * Exit the container:  ``exit``.
   * Exit the EC2 host:  ``exit``.

4. Check the dev website:  ``https://brain-score-web-dev-updated.kmk2mcntkw.us-east-2.elasticbeanstalk.com``.
5. If the dev website passes tests, deploy to production:  ``eb deploy brain-score-web-prod-updated --timeout 20``.
6. If necessary, repeat migrations, but this time begin with ``eb ssh brain-score-web-prod-updated``.

To Create Elastic Beanstalk Environments
****************************************

If the Elastic Beanstalk environments do not exist or need to be recreated::

    eb create brain-score-web-dev -c brain-score-web-dev -r us-east-2 -p Docker --envvars DEBUG=True,DOMAIN=localhost:brain-score-web-dev.us-east-2.elasticbeanstalk.com,DB_CRED=brainscore-1-ohio-cred

    eb create brain-score-web-prod -c brain-score-web-prod -r us-east-2 -p Docker --envvars DEBUG=False,DOMAIN=localhost:brain-score-web-prod.us-east-2.elasticbeanstalk.com:www.brain-score.org,DB_CRED=brainscore-prod-ohio-cred

