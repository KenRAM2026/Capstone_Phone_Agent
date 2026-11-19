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

        # Transactions: purchases on an account. The sort key starts with the
        # date (year-month-day sorts correctly as text) so items are stored in
        # date order; a Query newest-first with Limit 5 reads only 5 items.
        # The transaction id on the end keeps same-day purchases distinct.
        self.transactions_table = dynamodb.Table(
            self,
            "TransactionsTable",
            partition_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="date_txn_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Bank accounts on file: the only accounts payments and autopay may
        # use. A Query on customer_id lists a customer's bank accounts;
        # bank_account_id (sort key) tells them apart.
        self.bank_accounts_table = dynamodb.Table(
            self,
            "BankAccountsTable",
            partition_key=dynamodb.Attribute(
                name="customer_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="bank_account_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Payments: one item per confirmed payment. payment_id holds the
        # request ID created once at the caller's yes, so a retry arrives
        # with the same key and a conditional write ("only if this key does
        # not exist") refuses the duplicate instead of charging twice.
        # The conditional write itself is Lambda code, added later.
        self.payments_table = dynamodb.Table(
            self,
            "PaymentsTable",
            partition_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="payment_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Disputes: one item per disputed transaction. The (account_id,
        # transaction_id) pair is unique, so a conditional write ("only if
        # this key does not exist") refuses a second dispute on the same
        # transaction. The request ID is a normal attribute: Lambda uses it
        # to tell a retry (same request ID) from a genuine second attempt.
        self.disputes_table = dynamodb.Table(
            self,
            "DisputesTable",
            partition_key=dynamodb.Attribute(
                name="account_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="transaction_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Call state: one row per active call, keyed by the Connect call ID.
        # Lambda writes it each turn and deletes it at call end. expires_at is
        # the TTL backstop: DynamoDB removes the row after that time if the
        # hangup clearing failed. TTL deletion can lag, so Lambda must also
        # check expires_at itself. The TTL length is set in Lambda code.
        self.call_state_table = dynamodb.Table(
            self,
            "CallStateTable",
            partition_key=dynamodb.Attribute(
                name="call_id", type=dynamodb.AttributeType.STRING
            ),
            time_to_live_attribute="expires_at",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only: destroying the stack also deletes the table.
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Audit log: one item per important event in a call. A Query on
        # call_id returns that call's events in order. The sort key starts
        # with the date-time so events stay in order; the sequence number on
        # the end keeps two events in the same second distinct. Never store
        # verification values or full card numbers in these items.
        self.audit_log_table = dynamodb.Table(
            self,
            "AuditLogTable",
            partition_key=dynamodb.Attribute(
                name="call_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp_seq", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Mock data only. A real audit log would use RETAIN, since
            # deleting audit history defeats its purpose.
            removal_policy=RemovalPolicy.DESTROY,
        )
