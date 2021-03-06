=========================
Monitoring a workflow run
=========================


Once the step function passes the first step ('RunTaskAsem'), you can check the 'input' of the 'CheckTaskAwsem' which contains a field called 'jobid'. This is your job ID and you can check your S3 bucket to see if you can find a file named <jobid>.log. This will happen 5~10min after you start the process, because it takes time for an instance to be ready and send the log file to S3. The log file gets updated, so you can re-download this file and check the progress.

::

    aws s3 cp s3://suwang/<jobid>.log .

You can also ssh into your running instance. The 'instance_ip' field in the 'input' of 'CheckTaskAwsem' contains the IP.

::

    ssh ec2-user@<ip>  # if your CWL version is draft-3 (AMI is based on Amazon Linux)

    ssh ubuntu@<ip>  # if your CWL version is v1 (AMI is based on ubuntu)


The password is the password you entered as part of the input json (inside 'config' field, in this case, 'whateverpasswordworks') The purpose of the ssh is to monitor things, so refrain from doing various things there, which could interfere with the run. It is recommended, unless you're a developer, to use the log file than ssh.

You can also check from the Console the instance that is running which has a name awsem-<jobid>. It will terminate itself when the run finishes. You won't have access to terminate this or any other instance, but if something is hanging for too long, please contact the admin to resolve the issue.

When the run finishes successfully, you'll see in your bucket a file <jobid>.success. If there was an error, you will see a file <jobid>.error instead. The step functions will look green on every step, if the run was successful. If one of the steps is red, it means it failed at that step.


=========================  ======================
        Success                   Fail
=========================  ======================
|unicorn_stepfun_success|  |unicorn_stepfun_fail|
=========================  ======================

.. |unicorn_stepfun_success| image:: images/stepfunction_unicorn_screenshot.png
.. |unicorn_stepfun_fail| image:: images/stepfunction_unicorn_screenshot_fail.png


