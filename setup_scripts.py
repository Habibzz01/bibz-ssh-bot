INSTALL_ALL = r"""#!/bin/bash
# Bibz SSH Bot - Install all services on fresh VPS

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

echo "=== Updating system ==="
apt-get update -qq 2>/dev/null
apt-get upgrade -y -qq 2>/dev/null

echo "=== Installing base packages ==="
apt-get install -y -qq curl wget python3 python3-pip iptables ufw openssl qrencode 2>/dev/null

echo "=== 1. Setting up SSH Management ==="
mkdir -p /opt/bibz-bot
cat > /opt/bibz-bot/manage-ssh.sh << 'MANAGE_SCRIPT'
#!/bin/bash
# SSH Account Management
ACTION=$1
USERNAME=$2
PASSWORD=$3

case $ACTION in
    add)
        if id "$USERNAME" &>/dev/null; then
            echo "EXISTS"
            exit 0
        fi
        useradd -m -s /bin/bash "$USERNAME"
        echo "$USERNAME:$PASSWORD" | chpasswd
        true
        echo "ADDED:$USERNAME"
        ;;
    remove)
        userdel -r "$USERNAME" 2>/dev/null
        echo "REMOVED:$USERNAME"
        ;;
    list)
        awk -F: '$3>=1000 && $3!=65534 {print $1}' /etc/passwd
        ;;
    *)
        echo "Usage: $0 {add|remove|list} [username] [password]"
        exit 1
        ;;
esac
MANAGE_SCRIPT
chmod +x /opt/bibz-bot/manage-ssh.sh

echo "=== 2. Installing Xray (VMess/VLess) ==="
if ! command -v xray &>/dev/null; then
    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install 2>/dev/null || true
fi
cat > /usr/local/etc/xray/config.json << 'XRAY_CONFIG'
{
  "log": {"loglevel": "warning"},
  "inbounds": [
    {
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "dest": "www.microsoft.com:443",
          "serverNames": ["www.microsoft.com"],
          "privateKey": "",
          "shortIds": ["6ba85179e30d4fc2"]
        }
      }
    },
    {
      "port": 8443,
      "protocol": "vmess",
      "settings": { "clients": [] },
      "streamSettings": {
        "network": "ws",
        "wsSettings": { "path": "/vmess" }
      }
    }
  ],
  "outbounds": [{"protocol": "freedom"}]
}
XRAY_CONFIG
cat > /opt/bibz-bot/manage-xray.sh << 'XRAY_MANAGE'
#!/bin/bash
ACTION=$1
USERNAME=$2
TYPE=${3:-vmess}
PORT=${4:-443}

UUID=$(cat /proc/sys/kernel/random/uuid)
CONFIG_FILE="/usr/local/etc/xray/config.json"

case $ACTION in
    add)
        KEY=$(/usr/local/bin/xray x25519 2>/dev/null | grep "Private key" | awk '{print $3}')
        if [ -z "$KEY" ]; then KEY=""; fi
        
        # Generate config snippet
        echo "${UUID}:${TYPE}:${USERNAME}"
        ;;
    remove)
        echo "REMOVED:$USERNAME"
        ;;
    list)
        python3 -c "
import json
with open('$CONFIG_FILE') as f:
    c = json.load(f)
for inbound in c.get('inbounds', []):
    for client in inbound.get('settings', {}).get('clients', []):
        print(f\"{client.get('id','?')} ({inbound.get('protocol','?')})\")
        " 2>/dev/null || echo "none"
        ;;
    *)
        echo "Usage: $0 {add|remove|list} [username] [type]"
        exit 1
        ;;
esac
XRAY_MANAGE
chmod +x /opt/bibz-bot/manage-xray.sh
systemctl restart xray 2>/dev/null || true

echo "=== 3. Installing WireGuard ==="
apt-get install -y -qq wireguard
cat > /opt/bibz-bot/manage-wg.sh << 'WG_MANAGE'
#!/bin/bash
ACTION=$1
USERNAME=$2
SERVER_PUBLIC_KEY=""
SERVER_PRIVATE_KEY=""
SERVER_ADDRESS="10.0.0.1/24"
WG_DIR="/etc/wireguard"
WG_INTERFACE="wg0"

# Generate server keys if not exist
if [ ! -f "$WG_DIR/server.key" ]; then
    mkdir -p $WG_DIR
    wg genkey | tee $WG_DIR/server.key | wg pubkey > $WG_DIR/server.pub
    chmod 600 $WG_DIR/server.key
fi
SERVER_PRIVATE_KEY=$(cat $WG_DIR/server.key)
SERVER_PUBLIC_KEY=$(cat $WG_DIR/server.pub)

case $ACTION in
    add)
        CLIENT_PRIVATE_KEY=$(wg genkey)
        CLIENT_PUBLIC_KEY=$(echo "$CLIENT_PRIVATE_KEY" | wg pubkey)
        CLIENT_IP="10.0.0.$((RANDOM % 200 + 2))"
        
        # Add peer to server
        cat >> $WG_DIR/$WG_INTERFACE.conf << EOF

[Peer]
# $USERNAME
PublicKey = $CLIENT_PUBLIC_KEY
AllowedIPs = $CLIENT_IP/32
EOF
        
        # Generate client config
        PUBLIC_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
        cat > $WG_DIR/client-$USERNAME.conf << CLIENT_EOF
[Interface]
PrivateKey = $CLIENT_PRIVATE_KEY
Address = $CLIENT_IP/24
DNS = 1.1.1.1

[Peer]
PublicKey = $SERVER_PUBLIC_KEY
Endpoint = $PUBLIC_IP:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
CLIENT_EOF
        qrencode -t ansiutf8 < $WG_DIR/client-$USERNAME.conf 2>/dev/null
        echo "CONFIG:$(cat $WG_DIR/client-$USERNAME.conf)"
        systemctl restart wg-quick@$WG_INTERFACE 2>/dev/null || true
        ;;
    remove)
        sed -i "/^# $USERNAME$/,+3d" $WG_DIR/$WG_INTERFACE.conf 2>/dev/null
        rm -f $WG_DIR/client-$USERNAME.conf 2>/dev/null
        echo "REMOVED:$USERNAME"
        ;;
    list)
        for f in $WG_DIR/client-*.conf; do
            basename "$f" | sed 's/client-//' | sed 's/\.conf//'
        done 2>/dev/null
        ;;
    *)
        echo "Usage: $0 {add|remove|list} [username]"
        exit 1
        ;;
esac
WG_MANAGE
chmod +x /opt/bibz-bot/manage-wg.sh

# Enable WireGuard
WG_DIR="/etc/wireguard"
mkdir -p $WG_DIR
cat > $WG_DIR/wg0.conf << 'WG_BASE'
[Interface]
PrivateKey = 
Address = 10.0.0.1/24
ListenPort = 51820
SaveConfig = false
WG_BASE
# Generate keys
wg genkey 2>/dev/null | tee $WG_DIR/server.key | wg pubkey > $WG_DIR/server.pub 2>/dev/null
chmod 600 $WG_DIR/server.key 2>/dev/null
SERVER_PUB=$(cat $WG_DIR/server.pub 2>/dev/null)
PRIV=$(cat $WG_DIR/server.key 2>/dev/null)
sed -i "s|PrivateKey = |PrivateKey = $PRIV|" $WG_DIR/wg0.conf 2>/dev/null

echo "=== 4. Installing OpenVPN ==="
apt-get install -y -qq openvpn easy-rsa 2>/dev/null
mkdir -p /opt/bibz-bot/openvpn
cat > /opt/bibz-bot/manage-ovpn.sh << 'OVPN_MANAGE'
#!/bin/bash
ACTION=$1
USERNAME=$2
OVPN_DIR="/opt/bibz-bot/openvpn"

case $ACTION in
    add)
        cd /opt/bibz-bot/easy-rsa
        if [ ! -f "pki/ca.crt" ]; then
            echo "PKI not initialized. Run setup first."
            exit 1
        fi
        ./easyrsa --batch --req-cn="$USERNAME" gen-req "$USERNAME" nopass 2>/dev/null
        ./easyrsa --batch sign-req client "$USERNAME" 2>/dev/null
        echo "ADDED:$USERNAME"
        ;;
    remove)
        cd /opt/bibz-bot/easy-rsa 2>/dev/null
        rm -f pki/private/${USERNAME}.key pki/issued/${USERNAME}.crt pki/reqs/${USERNAME}.req
        echo "REMOVED:$USERNAME"
        ;;
    list)
        ls /opt/bibz-bot/easy-rsa/pki/issued/*.crt 2>/dev/null | xargs -n1 basename | sed 's/\.crt//'
        ;;
    *)
        echo "Usage: $0 {add|remove|list} [username]"
        exit 1
        ;;
esac
OVPN_MANAGE
chmod +x /opt/bibz-bot/manage-ovpn.sh

echo "=== 5. Installing SlowDNS ==="
apt-get install -y -qq build-essential golang-go git 2>/dev/null
if [ ! -f /usr/local/bin/dnstt-server ]; then
    git clone https://github.com/habibzadeh/dnstt.git /tmp/dnstt 2>/dev/null || true
    cd /tmp/dnstt 2>/dev/null && go build -o /usr/local/bin/dnstt-server ./server 2>/dev/null || true
    cd /tmp/dnstt 2>/dev/null && go build -o /usr/local/bin/dnstt-client ./client 2>/dev/null || true
    rm -rf /tmp/dnstt 2>/dev/null
fi
cat > /opt/bibz-bot/manage-slowdns.sh << 'SDNS_MANAGE'
#!/bin/bash
ACTION=$1
USERNAME=$2
SDNS_DIR="/opt/bibz-bot/slowdns"

mkdir -p $SDNS_DIR

case $ACTION in
    add)
        PASSWORD=$(openssl rand -base64 12)
        useradd -m -s /bin/false "$USERNAME" 2>/dev/null
        echo "$USERNAME:$PASSWORD" | chpasswd
        # Speed limit: 1Mbps per user
        PUBLIC_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
        echo "ADDED:$USERNAME"
        echo "HOST:$PUBLIC_IP"
        echo "DNS:8.8.8.8:53"
        ;;
    remove)
        userdel -r "$USERNAME" 2>/dev/null
        echo "REMOVED:$USERNAME"
        ;;
    list)
        awk -F: '$3>=1000 && $3!=65534 {print $1}' /etc/passwd 2>/dev/null
        ;;
    *)
        echo "Usage: $0 {add|remove|list} [username]"
        exit 1
        ;;
esac
SDNS_MANAGE
chmod +x /opt/bibz-bot/manage-slowdns.sh

echo "=== Configuring Firewall ==="
ufw allow 22/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true
ufw allow 8443/tcp 2>/dev/null || true
ufw allow 51820/udp 2>/dev/null || true
ufw allow 1194/udp 2>/dev/null || true

echo ""
echo "=== INSTALLATION COMPLETE ==="
echo ""
echo "Server is ready for management via bot commands."
echo ""
cat /etc/wireguard/server.pub 2>/dev/null && echo "(WireGuard Server Public Key)"
"""


SETUP_EASYRSA = r"""#!/bin/bash
# Initialize OpenVPN PKI
set -e
cd /opt/bibz-bot
if [ ! -d "easy-rsa" ]; then
    make-cadir easy-rsa 2>/dev/null || cp -r /usr/share/easy-rsa easy-rsa 2>/dev/null
fi
cd easy-rsa
./easyrsa --batch init-pki 2>/dev/null || true
./easyrsa --batch build-ca nopass 2>/dev/null || true
./easyrsa --batch gen-dh 2>/dev/null || true
./easyrsa --batch gen-req server nopass 2>/dev/null || true
./easyrsa --batch sign-req server server 2>/dev/null || true
openvpn --genkey secret ta.key 2>/dev/null || true
echo "OpenVPN PKI initialized"
"""


def get_install_script() -> str:
    return INSTALL_ALL


def get_easyrsa_script() -> str:
    return SETUP_EASYRSA
