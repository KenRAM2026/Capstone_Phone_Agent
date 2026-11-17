import aws_cdk as core
import aws_cdk.assertions as assertions

from infra.infra_stack import InfraStack


def test_customer_table_keys_and_phone_index():
    app = core.App()
    stack = InfraStack(app, "infra")
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [{"AttributeName": "customer_id", "KeyType": "HASH"}],
            "BillingMode": "PAY_PER_REQUEST",
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "phone_number-index",
                    "KeySchema": [
                        {"AttributeName": "phone_number", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                }
            ],
        },
    )
