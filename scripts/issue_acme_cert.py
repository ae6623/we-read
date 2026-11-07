#!/usr/bin/env python3
"""用 ACME HTTP-01 给七牛 CDN 域名签一张 Let's Encrypt 免费证书。

原理：七牛 CDN 回源到对象存储，所以把 ACME 的验证文件上传到 bucket 的
`.well-known/acme-challenge/<token>`，Let's Encrypt 就能从公网读到来完成验证，
不需要服务器、不需要管理员权限。

产物：$TEMP/acme-out/ 下 fullchain.pem 与 privkey.pem
之后用七牛 API 上传证书并绑定到域名。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import josepy as jose
from acme import challenges, client, crypto_util, errors, messages
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from qiniu import Auth as QAuth
from qiniu import BucketManager, put_file_v2

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "reader.js-dev.cn"
BUCKET = "we-read-assets"
OUT = Path(os.environ.get("TEMP", ".")) / "acme-out"
OUT.mkdir(parents=True, exist_ok=True)

AK = os.environ["QINIU_AK"]
SK = os.environ["QINIU_SK"]
qauth = QAuth(AK, SK)

DIRECTORY = "https://acme-v02.api.letsencrypt.org/directory"


def net_get(url):  # 走系统代理
    import urllib.request

    return urllib.request.urlopen(url, timeout=30).read()


def upload_challenge(token: str, key_auth: str) -> None:
    tmp = OUT / f"chal-{token}"
    tmp.write_text(key_auth, encoding="utf-8")
    key = f".well-known/acme-challenge/{token}"
    for attempt in range(5):
        ret, info = put_file_v2(qauth.upload_token(BUCKET, key, 600), key, str(tmp))
        if info.status_code == 200:
            tmp.unlink(missing_ok=True)
            print(f"  已上传挑战文件 {key}")
            return
        time.sleep(2)
    tmp.unlink(missing_ok=True)
    raise RuntimeError(f"上传挑战文件失败: {info.status_code}")


def main() -> int:
    # 1. 账号密钥
    account_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jose.JWKRSA(key=account_key)

    net = client.ClientNetwork(jwk, user_agent="we-read-acme/1.0")
    directory = messages.Directory.from_json(net.get(DIRECTORY).json())
    acme_client = client.ClientV2(directory, net=net)

    try:
        regr = acme_client.new_account(
            messages.NewRegistration.from_data(email="admin@js-dev.cn", terms_of_service_agreed=True)
        )
        print("账号注册成功")
    except errors.ConflictError as e:
        regr = e.location
        print("账号已存在，复用")

    # 2. 先生成域名私钥 + CSR（新版 acme 用 CSR 下单）
    domain_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr_pem = crypto_util.make_csr(
        domain_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        [DOMAIN],
    )
    order = acme_client.new_order(csr_pem)
    print(f"订单已创建: {order.uri}")

    # 3. 选 HTTP-01 挑战
    authz = order.authorizations[0]
    http_chall = None
    for chall in authz.body.challenges:
        if isinstance(chall.chall, challenges.HTTP01):
            http_chall = chall
            break
    if http_chall is None:
        print("没有可用的 HTTP-01 挑战", file=sys.stderr)
        return 1

    token = http_chall.chall.path.split("/")[-1]
    key_auth = http_chall.chall.key_authorization(jwk)
    print(f"挑战 token: {token}")
    upload_challenge(token, key_auth)

    # 4. 响应挑战并轮询
    acme_client.answer_challenge(http_chall, http_chall.response(jwk))
    deadline = time.time() + 180
    while time.time() < deadline:
        authz, _ = acme_client.poll(authz)
        if authz.body.status == messages.STATUS_VALID:
            print("授权通过")
            break
        if authz.body.status == messages.STATUS_INVALID:
            print(f"授权失败: {authz.body.error}", file=sys.stderr)
            return 1
        time.sleep(3)
    else:
        print("授权超时", file=sys.stderr)
        return 1

    # 5. 完成订单
    import datetime as _dt
    order = acme_client.poll_and_finalize(order, deadline=_dt.datetime.now() + _dt.timedelta(minutes=3))
    print("证书已签发")

    # 6. 落盘
    (OUT / "fullchain.pem").write_text(order.fullchain_pem, encoding="utf-8")
    (OUT / "privkey.pem").write_text(
        domain_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode(),
        encoding="utf-8",
    )
    cert_only = crypto_util.cert_and_chain_from_fullchain(order.fullchain_pem)[0]
    (OUT / "cert.pem").write_text(cert_only, encoding="utf-8")

    # 7. 清理挑战文件
    try:
        key = f".well-known/acme-challenge/{token}"
        BucketManager(qauth).delete(BUCKET, key)
    except Exception:
        pass

    print(f"完成，证书在 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
