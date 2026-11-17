from aws_cdk import RemovalPolicy, aws_dynamodb as dynamodb
from constructs import Construct


class DataTables(Construct):
    """DynamoDB tables for the mock bank data layer."""

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        # Customer: looked up by customer_id (GetItem) or, from caller ID,
        # by phone_number through the GSI (Query).
        self.customer_table = dynamodb.Table(
            self,
            "CustomerTable",
            partition_key=dynamodb.Attribute(
                name="customer_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # phone_number is not unique, so a Query may return several customers.
        # Keys-only projection: returns customer_id, then GetItem for the rest.
        self.customer_table.add_global_secondary_index(
            index_name="phone_number-index",
            partition_key=dynamodb.Attribute(
                name="phone_number", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.KEYS_ONLY,
        )
