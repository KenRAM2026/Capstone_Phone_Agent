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

        # Accounts: one customer can have several accounts. A Query on
        # customer_id returns all of that customer's accounts; account_id
        # (sort key) tells them apart inside the customer's partition.
        self.accounts_table = dynamodb.Table(
            self,
            "AccountsTable",
            partition_key=dynamodb.Attribute(
                name="customer_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Cards: physical cards on an account. A Query on account_id lists
        # every card on the account; card_id (sort key) tells them apart.
        self.cards_table = dynamodb.Table(
            self,
            "CardsTable",
            partition_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="card_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Identify fallback: the caller says the last 4 of their card. last4 is
        # not unique, so a Query may return several cards (a shortlist that
        # verification narrows down). Keys-only: returns account_id and card_id.
        self.cards_table.add_global_secondary_index(
            index_name="last4-index",
            partition_key=dynamodb.Attribute(
                name="last4", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.KEYS_ONLY,
        )
