
module="$1"
repo="$2"
OWNER="$3"
#拉取代码，加入cicd相关文件，push到远端
git clone ${repo}
cd glance
git checkout -b stable/2023.2 origin/stable/2023.2
git checkout -b develop
cp ../Jenkinsfile .
cp -r ../.github/ .
sed -i "s/cinder/${module}/g" Jenkinsfile
sed -i "s/cinder/${module}/g" ./.github/workflows/kolla_build.yml

git  add .
git commit -m "Add cicd"
git push --set-upstream origin develop

#创建jenkins上的流水线
cat <<EOF > multibranch_config.xml
<org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject plugin="workflow-multibranch@2.x">
  <actions/>
  <description>Multibranch pipeline for glance</description>
  <properties/>
  <folderViews class="com.cloudbees.hudson.plugins.folder.views.DefaultFolderViewHolder" plugin="cloudbees-folder@6.x">
    <views>
      <hudson.model.AllView>
        <name>All</name>
        <filterExecutors>false</filterExecutors>
        <filterQueue>false</filterQueue>
        <properties class="hudson.model.View\$PropertyList"/>
      </hudson.model.AllView>
    </views>
    <tabBar class="hudson.views.DefaultViewsTabBar"/>
  </folderViews>
  <healthMetrics>
    <com.cloudbees.hudson.plugins.folder.health.WorstChildHealthMetric>
      <nonRecursive>false</nonRecursive>
    </com.cloudbees.hudson.plugins.folder.health.WorstChildHealthMetric>
  </healthMetrics>
  <icon class="com.cloudbees.folder.icons.StockFolderIcon"/>
  <orphanedItemStrategy class="com.cloudbees.hudson.plugins.folder.computed.DefaultOrphanedItemStrategy">
    <pruneDeadBranches>true</pruneDeadBranches>
    <daysToKeep>-1</daysToKeep>
    <numToKeep>-1</numToKeep>
  </orphanedItemStrategy>
  <triggers>
    <com.cloudbees.hudson.plugins.folder.computed.PeriodicFolderTrigger>
      <spec>H/5 * * * *</spec>
      <interval>86400000</interval>
    </com.cloudbees.hudson.plugins.folder.computed.PeriodicFolderTrigger>
  </triggers>
  <sources>
    <jenkins.branch.BranchSource>
      <source class="org.jenkinsci.plugins.github_branch_source.GitHubSCMSource">
        <id>${module}-github</id>
        <repoOwner>${OWNER}</repoOwner>
        <repository>${module}.git</repository>
        <credentialsId>dsy_github_token</credentialsId>
        <traits>
          <org.jenkinsci.plugins.github__branch__source.BranchDiscoveryTrait>
            <strategyId>3</strategyId>
          </org.jenkinsci.plugins.github__branch__source.BranchDiscoveryTrait>
          <org.jenkinsci.plugins.github__branch__source.TagDiscoveryTrait/>
        </traits>
      </source>
      <strategy class="jenkins.branch.DefaultBranchPropertyStrategy">
        <properties class="empty-list"/>
      </strategy>
    </jenkins.branch.BranchSource>
  </sources>
  <factory class="org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory">
    <scriptPath>Jenkinsfile</scriptPath>
  </factory>
</org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject>
EOF
JENKINS_URL="http://172.20.3.27:8085"
USERNAME="dingo"
APITOKEN="11eb1b56de596831ce28080a56f1354fa9"
# 获取 crumb
CRUMB=$(curl -s -u "${USERNAME}:${APITOKEN}" \
    "${JENKINS_URL}/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)")

# 2. 使用获取的 crumb 创建流水线
curl -u "${USERNAME}:${APITOKEN}" \
    -H "$CRUMB" \
    -X POST \
    -H "Content-Type: application/xml" \
    --data-binary @multibranch_config.xml \
    "${JENKINS_URL}/view/dingoops/createItem?name=${module}_pipeline"

GITHUB_TOKEN="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"
OWNER="dsy3502"
REPO=${module}
JENKINS_HOOK_URL="https://3f59-2602-feda-30-cafe-1602-ecff-fe49-2fb4.ngrok-free.app/generic-webhook-trigger/invoke?token=${module}"

# 配置 github项目的webhook
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/${OWNER}/${REPO}/hooks \
  -d '{
    "name": "web",
    "active": true,
    "events": ["Workflow runs"],
    "config": {
      "url": "'${JENKINS_HOOK_URL}'",
      "content_type": "json",
      "insecure_ssl": "0"
    }
  }'


# 获取公钥信息
KEY_INFO=$(curl -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  https://api.github.com/repos/${OWNER}/${REPO}/actions/secrets/public-key)

KEY_ID=$(echo $KEY_INFO | jq -r .key_id)
PUBLIC_KEY=$(echo $KEY_INFO | jq -r .key)

# 2. 使用sodium_crypto加密值(需要安装libsodium)


# 2. 获取最新公钥
PUBLIC_KEY_INFO=$(curl -s \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/secrets/public-key")

KEY=$(echo $PUBLIC_KEY_INFO | jq -r .key)
KEY_ID=$(echo $PUBLIC_KEY_INFO | jq -r .key_id)

# 3. 创建 Python 加密脚本
cat > encrypt_secret.py << 'EOF'
import base64
import sys
from nacl import encoding, public

def encrypt(public_key, secret_value):
    public_key = public.PublicKey(base64.b64decode(public_key))
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

if __name__ == "__main__":
    print(encrypt(sys.argv[1], sys.argv[2]))
EOF

# 4. 加密并创建 secrets
USERNAME_ENCRYPTED=$(python encrypt_secret.py "$KEY" "dongshanyi")
TOKEN_ENCRYPTED=$(python encrypt_secret.py "$KEY" "dckr_pat_q1sjw9ayjk3xvsbPFwqic4OpJSE")
REGISTRY_ENCRYPTED=$(python encrypt_secret.py "$KEY" "docker.io")
# 5. 创建 secrets
curl -X PUT \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/secrets/DOCKERHUB_USERNAME" \
  -d "{\"encrypted_value\":\"${USERNAME_ENCRYPTED}\",\"key_id\":\"${KEY_ID}\"}"

curl -X PUT \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/secrets/DOCKERHUB_TOKEN" \
  -d "{\"encrypted_value\":\"${TOKEN_ENCRYPTED}\",\"key_id\":\"${KEY_ID}\"}"

curl -X PUT \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/actions/secrets/DOCKER_REGISTRY" \
  -d "{\"encrypted_value\":\"${REGISTRY_ENCRYPTED}\",\"key_id\":\"${KEY_ID}\"}"
