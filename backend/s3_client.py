import boto3


def build_s3(aws_access_key_id: str, aws_secret_access_key: str, region: str):
    return boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region,
    )


def s3_upload_bytes(s3, data: bytes, bucket: str, key: str, content_type: str = "application/octet-stream", make_public: bool = False) -> str:
    extra = {"ContentType": content_type}
    if make_public:
        extra["ACL"] = "public-read"
    s3.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return key


def s3_public_url(bucket: str, region: str, key: str) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def s3_presigned_url(s3, bucket: str, key: str, expiry: int = 604800) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry,
    )


def s3_object_url(s3, bucket: str, region: str, key: str, make_public: bool, expiry: int = 604800) -> str:
    if make_public:
        return s3_public_url(bucket, region, key)
    return s3_presigned_url(s3, bucket, key, expiry)
