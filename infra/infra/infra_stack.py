from aws_cdk import Stack
from constructs import Construct

from infra.data_tables import DataTables


class InfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.data_tables = DataTables(self, "DataTables")
