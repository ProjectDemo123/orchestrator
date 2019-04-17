from kafka import KafkaConsumer,KafkaProducer
from flask import Flask, request, send_file
from flask_cors import CORS
from . import jenkins
import threading
import logging
import time
import json
import os
import sys
import traceback
import requests

GROUP_ID='orchestrator'
TOPIC_ID='ci_ops'
TOPIC_ID_WORKERS='necessity'

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": '*'}})

class Producer(object):
    def __init__(self, kafka_brokers):
        self.producer = KafkaProducer(
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            bootstrap_servers=kafka_brokers
        )
    def send_message(self,topic,data):
        self.producer.send(topic, data)

class Consumer(threading.Thread):
    daemon = True
    def __init__(self,kafka_brokers,producer):
        super(Consumer, self).__init__()
        self.kafka_brokers=kafka_brokers
        self.producer=producer
        self.logger=logging.getLogger()
    def run(self):
        while(True):
            consumer = KafkaConsumer(bootstrap_servers=self.kafka_brokers,
                                    group_id=GROUP_ID,
                                    enable_auto_commit=True,
                                    auto_offset_reset='earliest')
            consumer.subscribe([TOPIC_ID])
            self.logger.info("Orchestrator Listerners Activated/Re-activated Successfully")
            rx_message = ''
            try:
                for message in consumer:
                    rx_message=json.loads(message.value.decode('utf-8'))
                    self.logger.info("Received Message in Topic {} - Group {} : {}".format(message.topic, GROUP_ID, rx_message))
                    if(rx_message != ""):
                        consumer.commit()
                        break
                consumer.close()
                if(rx_message != ""):
                        self.platform_handler(rx_message)
            except:
                consumer.close()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                self.logger.info('Error Occured While Processing IDP Kafka Message Response. Please refer following stacktrace for more details \n')
                self.logger.info(''.join(line for line in lines))
            finally:
                self.logger.info("Consumed Message Successfully")

    def platform_handler(self,idp_message):
        self.logger.info(idp_message['targetplatform'].lower().strip())
        if(idp_message['targetplatform'].lower().strip() == "jenkins"):
            self.logger.info("Invoking Jenkins CI")
            if(idp_message['action'].lower().strip() == "create" or idp_message['action'].lower().strip() == "edit"):
                self.logger.info("Invoke Jenkins Create/Edit Module")
                self.logger.info(jenkins.createJob(idp_message['idpjson']))
            elif(idp_message['action'].lower().strip() == "trigger"):
                self.logger.info("Invoke Jenkins Trigger Module") 
                self.logger.info(jenkins.triggerJob(idp_message['idpjson']))
        elif(idp_message['targetplatform'].lower().strip() == "necessity"):
            self.logger.info("Invoking Necessity CI")
            if(idp_message['action'].lower().strip() == "trigger"):
                self.logger.info("Invoke Necessity Trigger Module")
                self.producer.send_message(TOPIC_ID_WORKERS, idp_message['idpjson'])
                self.logger.info("Necessity Trigger Module Task Submission Success")
        else:
            self.logger.info("Sleeping for 10...")
            time.sleep(10)

class Main(object):
    def __init__(self):
        if 'KAFKA_CLUSTER' in os.environ:
            kafka_brokers = os.environ['KAFKA_CLUSTER'].split(',')
        else:
            raise ValueError('KAFKA_CLUSTER environment variable not set')
        logging.basicConfig(
            format='%(asctime)s  %(levelname)s  %(process)d --- [%(thread)d]  %(name)s : %(message)s',
            level=logging.INFO
        )
        self.logger = logging.getLogger()
        self.logger.info("Activating Orchestrator Server")
        self.logger.info("Initializing Kafka Producer")
        self.logger.info("KAFKA_BROKERS={0}".format(kafka_brokers))
        self.producer = Producer(kafka_brokers)
        self.logger.info("Activating Orchestrator Listerners")
        threads = [Consumer(kafka_brokers,self.producer)]
        for t in threads:
            t.start()

    @app.route("/orchestrator/artifacts/add", methods=['POST'])
    def addArtifactoryRepoGlobConf():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.addArtifactoryRepoGlobConf(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')

    @app.route("/orchestrator/artifacts/download", methods=['POST'])
    def downloadArtifacts():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.downloadArtifacts(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')

    @app.route("/orchestrator/config/add/alm/config", methods=['POST'])
    def addALMConfig():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.addALMConfig(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')
    
    @app.route("/orchestrator/config/get/stageviewurl", methods=['POST'])
    def getStageViewUrl():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.getStageViewUrl(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')
    
    @app.route("/orchestrator/config/get/jobjson", methods=['POST'])
    def getJobJSON():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.getJobJSON(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')
    
    @app.route("/orchestrator/job/disableJob", methods=['POST'])
    def disableJob():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.disableJob(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')
    
    @app.route("/orchestrator/job/apprRejectJobs", methods=['POST'])
    def apprRejectJobs():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.apprRejectJobs(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')
    
    @app.route("/orchestrator/job/get/status", methods=['POST'])
    def getBuildStatus():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.getBuildStatus(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')

    @app.route("/orchestrator/role/create", methods=['POST'])
    def createRole():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.createRole(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')

    @app.route("/orchestrator/slave/copy", methods=['POST'])
    def copySlave():
        if(request.get_json()['targetplatform'] == "jenkins"):
            return jenkins.copySlave(request.get_json())
        return app.response_class(response = "-1", status=500, mimetype='text/plain')

    @app.route("/orchestrator/slave/get/status", methods=['POST'])
    def getSlaveStatus():
        if(request.get_json()['targetplatform'].lower().strip() == "jenkins"):
            return app.response_class(response = jenkins.getSlaveStatus(request.get_json()), status=200, mimetype='text/plain')
        return app.response_class(response = "-1", status=500, mimetype='text/plain')

    def run(self):
        try:
            self.logger.info("Orchestrator Server Started")
            app.run(host='0.0.0.0', port=8281)
        except KeyboardInterrupt:
            self.logger.info("Shutdown Command Received. Preparing for graceful shutdown")
            self.logger.info("Shutdown Completed. Bye !")

if __name__ == "__main__":
    Main().run()