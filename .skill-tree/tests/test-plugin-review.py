"""Optional pilot116 requirements-led deterministic integration tests.

Synthetic host evidence tests deterministic integration only. No native actor,
provider, benchmark or upstream helper runs. The fixtures establish no actual host invocation or candidate efficacy.

The owned invocation policy and producer context-end evidence remain separate
from ordinary parameters, replaceable extra instructions and actor result data.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

CORE=next(p for p in Path(__file__).resolve().parents if (p/'lib/plugin-runtime.js').is_file())
RAW=CORE/'tests/fixtures/ponytail'
PIN='96608e078b2d5ea607c5c3b8b5a54d1c1fba6846'
ENTRY='skills/ponytail/SKILL.md'
ENTRY_SHA='9badd22a32e19cb884e46dfa8d3aae82bb81dfa5484105b8b4f0262df823a509'
LICENSE_SHA='fb1bc6909ac3ef82d5c22106e32ef682b0cff66788fa915fb9b53b15c9d2f3ab'
OP='skill-tree-pr-review-cycle'
OCCURRENCE='ponytail-review-once'
POLICY={'schema':1,'kind':'report-only','context_lifetime':'single-attempt',
        'fresh_context_per_attempt':True,'require_context_end':True,
        'allowed_tools':['read-pinned-resources','read-scoped-context'],
        'allowed_actions':['return-proposals']}

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module

# Reuse actual authored workflow/current engine, not mock return dictionaries.
wf=load('pilot_requirements_workflow',CORE/'common/scripts/workflow-state.py')
pr=load('pilot_requirements_pr',CORE/'common/scripts/pr-review-state.py')

def engine():return load('pilot_requirements_engine',CORE/'common/scripts/plugin-invocation.py')

INSTALL=r"""const fs=require('node:fs'),path=require('node:path');
const core=process.argv[1],root=process.argv[2],raw=process.argv[3],options=JSON.parse(process.argv[4]);
const installation=require(path.join(core,'lib/installation.js'));
const lifecycle=require(path.join(core,'lib/plugin-lifecycle.js'));
const operation='skill-tree-pr-review-cycle';
installation.install(root,core,options.flavor||'general',[{name:operation,provider:'codex',rel:'.agents/skills/'+operation}]);
(async()=>{
 if(options.selected){
  // Install the actual owned pilot descriptor; fixture parameter layers cannot
  // supply or replace its immutable policy.
  const definition=JSON.parse(fs.readFileSync(path.join(core,'config/plugins/ponytail.json'),'utf8'));
  definition.adapter.parameter_defaults.upstream.instructions='UPSTREAM-EXTRA';
  definition.adapter.parameter_defaults.project={values:{fixture:true}};
  const acquire=async request=>({revision:options.pin,files:{[options.entry]:fs.readFileSync(path.join(raw,options.entry)),LICENSE:fs.readFileSync(path.join(raw,'LICENSE'))}});
  const proposal=await lifecycle.prepareProposal(root,{request_id:'pilot-owned-install',operation:'install',sources:[definition],
    bindings:options.bindings||[{id:options.occurrence,plugin_id:'ponytail',operation,anchor:options.anchor,enabled:options.enabled,
      parameters:{fixture_ordinary_parameter:'kept'},instructions:options.instructions}]},{acquire});
  lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});
  installation.refresh(root,core);
 }
 process.stdout.write(JSON.stringify({package_root:path.join(root,'.agents/skills',operation)}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
"""

class PluginReviewPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.sequence=0;self.decision_sequence=0

    def install(self,*,selected=True,enabled=True,anchor='after',flavor='general',instructions='BINDING-EXTRA',bindings=None,run_overrides=None,source=CORE):
        self.pilot_policy=json.loads((CORE/'config/plugins/ponytail.json').read_text())['adapter']['invocation_policy']
        self.sequence+=1;self.root=self.base/('case-'+str(self.sequence));self.root.mkdir()
        subprocess.run(['git','init','-q',str(self.root)],check=True,capture_output=True)
        (self.root/'package.json').write_text(json.dumps({'scripts':{'test':'node --test'}}))
        (self.root/'source.py').write_text('def value():\n    return 1\n')
        options={'selected':selected,'enabled':enabled,'anchor':anchor,'flavor':flavor,
                 'pin':PIN,'entry':ENTRY,'entry_sha':ENTRY_SHA,'license_sha':LICENSE_SHA,
                 'occurrence':OCCURRENCE,'instructions':instructions,'bindings':bindings}
        result=subprocess.run(['node','-e',INSTALL,str(source),str(self.root),str(RAW),json.dumps(options)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.package_root=Path(json.loads(result.stdout)['package_root'])
        self.pr_script=self.package_root/'scripts/pr-review-state.py'
        self.store=wf.Store(self.root,allow_unselected=True,neutral=True,route_queue=False)
        self.anchor=anchor;self.capabilities=['codex-source-backed-context']
        self.publication_id='d'*32
        self.publication=self.root/'.skill-tree/history/publications'/('pub-'+self.publication_id+'.json')
        self.snapshot={'repo_id':'pilot-fixture-repository','remote':'origin',
            'source_branch':'feature/pilot-fixture','target_branch':'develop',
            'head':'a'*40,'base_oid':'b'*40,'changed_files':['source.py'],
            'pr':{'id':'PR-pilot-fixture','number':1,'url':'https://example.invalid/pr/1'},
            'state':'OPEN','threads':[],'reviews':[],'comments':[],
            'checks':[{'name':'fixture-check','required':True,'status':'success'}],
            'checks_known':True,'approvals_known':True,'approvals_required':False,
            'approved':True,'mergeable':'MERGEABLE'}
        self.cli('init',merge=True,instruction='Synthetic fixture PR cycle with merge.',
                 run_overrides=run_overrides or {})
        self.assertTrue(self.publication.is_file(),'An actual owned publication carrier is required.')
        self.assertEqual(self.read_publication()['pr']['id'],'PR-pilot-fixture')

    def cli(self,command,ok=True,**extra):
        request=self.root/'fixture-pr-input.json'
        request.write_text(json.dumps({'snapshot':self.snapshot,**extra}))
        result=subprocess.run(['python3','-I','-B',str(self.pr_script),command,str(self.root),
            '--publication-id',self.publication_id,'--input',str(request)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0 if ok else 2,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def read_publication(self):return json.loads(self.publication.read_text())

    def core_review(self,findings=None):
        return self.cli('review',review={'head':self.snapshot['head'],'base_oid':self.snapshot['base_oid'],
            'target_branch':self.snapshot['target_branch'],'files':self.snapshot['changed_files'],
            'context_inspected':True,'discussions_inspected':True,'checks_inspected':True,
            'findings':findings or [],'evidence':['Synthetic full core diff/context/check observation.']})

    def core_inspection(self):
        return self.cli('inspection',inspection={'head':self.snapshot['head'],
            'base_oid':self.snapshot['base_oid'],'target_branch':self.snapshot['target_branch'],
            'files':self.snapshot['changed_files'],'context_inspected':True,
            'discussions_inspected':True,'checks_inspected':True,
            'evidence':['Synthetic first full core inspection; final review remains outstanding.']})

    def disable(self):
        # Use the owned manager and its derived refresh for real configuration edits.
        change=r"""const path=require('node:path');
const core=process.argv[1],root=process.argv[2],id=process.argv[3];
const lifecycle=require(path.join(core,'lib/plugin-lifecycle.js'));
const installation=require(path.join(core,'lib/installation.js'));
(async()=>{const proposal=await lifecycle.prepareProposal(root,{
 request_id:'pilot-explicit-disable',operation:'disable',binding_ids:[id]});
 lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});
 installation.refresh(root,core);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});"""
        result=subprocess.run(['node','-e',change,str(CORE),str(self.root),OCCURRENCE],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        registry=json.loads((self.root/'.skill-tree/installation/plugins.json').read_text())
        self.assertFalse(registry['bindings'][0]['enabled'])

    def uninstall(self):
        change=r"""const path=require('node:path');
const core=process.argv[1],root=process.argv[2];
const lifecycle=require(path.join(core,'lib/plugin-lifecycle.js'));
const installation=require(path.join(core,'lib/installation.js'));
(async()=>{const proposal=await lifecycle.prepareProposal(root,{
 request_id:'pilot-explicit-uninstall',operation:'uninstall',plugin_ids:['ponytail']});
 lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});
 installation.refresh(root,core);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});"""
        result=subprocess.run(['node','-e',change,str(CORE),str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        registry=json.loads((self.root/'.skill-tree/installation/plugins.json').read_text())
        self.assertEqual(registry['packages'],{});self.assertEqual(registry['bindings'],[])

    def technical_decision(self,context,answer='adopt',*,findings=False):
        # The actual DG producer/acceptance path uses declared synthetic provenance
        # in the temporary fixture; no fabricated successful receipt is supplied.
        self.decision_sequence+=1
        question={'id':'adopt-review-configuration','kind':'technical',
            'text':'Adopt the explicitly disabled current review configuration.',
            'options':[{'id':'adopt','text':'Adopt the inspected current configuration.'},
                       {'id':'keep','text':'Retain the frozen previous obligations.'}],
            'recommendation':'adopt','significance':'routine'}
        if findings:question={'id':'incorporate-review-findings','kind':'technical',
            'text':'Substantiate and incorporate the concrete returned review finding.',
            'options':[{'id':'incorporate','text':'Track the substantiated finding in ordinary core review.'},
                       {'id':'keep','text':'Leave the contribution unresolved.'}],
            'recommendation':'incorporate','significance':'routine'}
        record=wf.decision_action(self.store,'decision-start',{
            'request_id':'pilot-technical-decision-'+str(self.decision_sequence),'context':context,'mode':'manual',
            'question':question,
            'authority':{'id':'synthetic-review-config-grant','revision':1,'context_id':context['id'],
                'allowed_kinds':['technical'],
                'constraints':['Temporary unit fixture metadata only; no project installation or provider writes.'],
                'evidence':{'kind':'owner-message','reference':'Scripted unit fixture; no real owner consent.'}},
            'executor':{'id':'config-fixture-executor','context_id':'config-fixture-executor-context'}})
        def mutate(frame,command,**extra):
            return wf.decision_action(self.store,'decision-'+command,{
                'decision_id':frame['id'],'expected_decision_hash':frame['decision_hash'],
                'expected_decision_revision':frame['revision'],'expected_mode_epoch':frame['mode_epoch'],
                'expected_context_fingerprint':frame['context']['content_fingerprint'],**extra})
        actor={'id':'synthetic-fixture-owner','context_id':'synthetic-fixture-owner-context'}
        record=mutate(record,'prepare',role='owner',actor=actor)
        record=mutate(record,'record',attempt_id=record['prepared_attempt_id'],
            result={'status':'answered','answer':answer,'rationale':'The explicit fixture configuration choice is current.'},
            evidence={'kind':'submitted-answer','reference':'Synthetic unit answer; no actual human decision.',
                      'actor_id':actor['id'],'actor_context_id':actor['context_id']})
        return mutate(record,'accept')

    def generic_resolution_decision(self,chain,attempt):
        # Use the exact current generic DG context and the original chain grant;
        # a mismatched grant would reject incidentally and conceal the regression.
        context=wf._hook_resolution_context(chain['context'],chain,attempt,'hook-result-resolution')
        decision=wf.decision_action(self.store,'decision-start',{
            'request_id':'generic-resolution-review-control','context':context,
            'mode':chain['mode'],'authority':chain['authority'],'executor':chain['executor'],
            'question':{'id':'substantiate-pilot-finding','kind':'technical',
                'text':'Substantiate the finding for a future fix; no fix has been performed.',
                'options':[{'id':'accept','text':'Substantiate the finding; a fix remains outstanding.'},
                           {'id':'reject','text':'Do not substantiate the finding.'}],
                'recommendation':'accept','significance':'routine'}})
        def mutate(frame,command,**extra):
            return wf.decision_action(self.store,'decision-'+command,{
                'decision_id':frame['id'],'expected_decision_hash':frame['decision_hash'],
                'expected_decision_revision':frame['revision'],'expected_mode_epoch':frame['mode_epoch'],
                'expected_context_fingerprint':frame['context']['content_fingerprint'],**extra})
        actor={'id':'scripted-resolution-owner','context_id':'scripted-resolution-owner-context'}
        decision=mutate(decision,'prepare',role='owner',actor=actor)
        decision=mutate(decision,'record',attempt_id=decision['prepared_attempt_id'],
            result={'status':'answered','answer':'accept',
                'rationale':'Substantiate the finding; no fix, dismissal, verification or publication incorporation occurred.'},
            evidence={'kind':'submitted-answer','reference':'Synthetic temporary answer, not actual human approval.',
                      'actor_id':actor['id'],'actor_context_id':actor['context_id']})
        return mutate(decision,'accept')

    def start(self,*,request_id='pilot-chain',run_overrides=None,publication_bound=True):
        ctx=pr.hook_context(self.snapshot)
        grant={'id':'pilot-fixture-grant','revision':1,'context_id':ctx['id'],
            'allowed_kinds':['technical'],'constraints':['Synthetic local metadata only; no native actors or provider writes.'],
            'evidence':{'kind':'owner-message','reference':'Scripted fixture grant; no real owner approval.'}}
        request={'package_root':str(self.package_root),
            'request_id':request_id,
            'event':{'id':'pilot-event-'+request_id,'operation':OP,'anchor':self.anchor},
            'context':ctx,'mode':'manual','authority':grant,
            'executor':{'id':'pilot-executor','context_id':'pilot-executor-context'},
            'capabilities':self.capabilities,'run_overrides':run_overrides or {}}
        if publication_bound:request['publication_id']=self.publication_id
        return wf.hook_action(self.store,'hook-start',request)

    def change(self,frame,command,**extra):
        return wf.hook_action(self.store,'hook-'+command,{'chain_id':frame['id'],
            'expected_chain_hash':frame['chain_hash'],'expected_chain_revision':frame['revision'],
            'capabilities':self.capabilities,**extra})

    def prepare(self,frame,actor=None):
        actor=actor or {'id':'pilot-unit-actor-'+frame['id'],'context_id':'pilot-unit-context-'+frame['id']}
        return self.change(frame,'prepare',actor=actor,creation_evidence={
            'kind':'host-agent-created','provider':'controlled-unit-host','tool':'controlled-create',
            'reference':'Synthetic created-context record, not native qualification.',
            'actor_id':actor['id'],'actor_context_id':actor['context_id']})

    def attempt(self,frame):return frame['attempts'][frame['prepared_attempt_id']]

    def private_delivery(self,frame):
        a=self.attempt(frame)
        return wf._hook_node(self.package_root,{'runtime_action':'delivery-data','project_root':str(self.root),
            'configuration':frame['configuration'],'event':frame['event'],'context':frame['context'],
            'capabilities':self.capabilities,'adapter':{'provider':'codex','mechanism':'source-backed-context'},
            'chain_id':frame['id'],'attempt_id':a['id'],'binding_id':a['binding_id'],
            'public_input':a['input'],'input_digest':a['input_digest'],'mode':frame['mode'],'authority':frame['authority']})

    def invoke(self,frame,*,capture=None):
        a=self.attempt(frame);delivery=self.private_delivery(frame)
        evidence={'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-private-dispatch',
            'reference':'Synthetic real owned private-delivery callback; no native actor.',
            'actor_id':a['actor']['id'],'actor_context_id':a['actor']['context_id'],'mechanism':'source-backed-context'}
        args={'chain_id':frame['id'],'expected_chain_hash':frame['chain_hash'],
              'expected_chain_revision':frame['revision'],'attempt_id':a['id'],
              **{k:delivery[k] for k in ['input_digest','delivery_digest','resolved_parameter_digest']},'evidence':evidence}
        def sink(payload):
            self.assertFalse((self.store.base/'.writer-lock').exists())
            if capture is not None:capture.append(copy.deepcopy(payload))
        invoked=wf.hook_action(self.store,'hook-invoke',args,private_delivery_sink=sink)
        return invoked,delivery

    def context_end(self,frame):
        a=self.attempt(frame)
        return {'kind':'host-context-ended','provider':'controlled-unit-host','tool':'controlled-context-end',
            'reference':'Synthetic host-observed terminal context; not actor self-report.',
            'actor_id':a['actor']['id'],'actor_context_id':a['actor']['context_id'],
            'attempt_id':a['id'],'input_digest':a['input_digest'],'delivery_digest':a['delivery_digest'],
            'state':'ended'}

    def returned(self,frame,status='passed',*,capture=None,end='matching',result_extra=None):
        frame=self.prepare(frame);frame,delivery=self.invoke(frame,capture=capture);a=self.attempt(frame)
        ended=self.context_end(frame) if end=='matching' else end
        result={'status':status,**(result_extra or {})}
        evidence={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
            'reference':'Synthetic result; no actual native actor ran.',
            'actor_id':a['actor']['id'],'actor_context_id':a['actor']['context_id'],'mechanism':'source-backed-context'}
        args={'attempt_id':a['id'],**{k:delivery[k] for k in ['input_digest','delivery_digest','resolved_parameter_digest']},
              'result':result,'evidence':evidence}
        if ended is not None:args['context_end_evidence']=ended
        return self.change(frame,'record',**args),ended

    def accept(self,frame,end='matching',**extra):
        a=self.attempt(frame);args={'attempt_id':a['id'],'input_digest':a['input_digest'],**extra}
        if end=='matching':end=self.context_end(frame)
        if end is not None:args['context_end_evidence']=end
        return self.change(frame,'accept',**args)

    def complete(self,frame,*,attach=True,end='matching'):
        frame,ended=self.returned(frame,end=end)
        frame=self.accept(frame,end=ended)
        if frame['state']!='complete':
            frame=self.prepare(frame)
            self.assertEqual(frame['state'],'complete',
                'This fixture has one matching occurrence; remaining phases need actual not-selected skips.')
        if attach:self.cli('hook-attach',chain_id=frame['id'])
        return frame

    def held(self):
        previous=self.publication.read_bytes();result=self.cli('ready',ok=False)
        self.assertRegex(result['error'],r'(?i)hook|plugin|pilot|review|prerequisite|current|stale|configuration|resource|source|context|ownership|inventory|capability')
        self.assertEqual(self.publication.read_bytes(),previous,'A denied readiness cannot rewrite the live carrier.')

    def test_00_owned_enabled_live_publication_without_started_chain_blocks_readiness(self):
        # Original requirements-led Red used the owned CLI and reached incorrect pr-ready.
        self.install();self.core_review()
        self.assertFalse((self.root/'.skill-tree/invocations').exists())
        self.assertNotIn('hook_chains',self.read_publication())
        self.held()

    def test_core_only_real_owned_install_has_zero_packages_and_bindings(self):
        self.install(selected=False);self.core_review()
        manifest=json.loads((self.package_root/'references/plugin-bindings.json').read_text())
        self.assertEqual(manifest['packages'],{});self.assertEqual(manifest['bindings'],[])
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_selected_disabled_occurrence_is_not_reported_as_execution_success(self):
        self.install(enabled=False);self.core_review()
        self.assertEqual(self.cli('ready')['status'],'pr-ready')
        self.assertFalse((self.root/'.skill-tree/invocations').exists())
        self.assertNotIn('hook_chains',self.read_publication())

    def test_explicit_later_disable_cannot_erase_frozen_unstarted_obligation(self):
        self.install()
        self.disable()
        self.core_review()
        # Changing the persistent configuration is explicit, but has no accepted
        # publication-obligation reconciliation or previous successful execution.
        self.held()
        self.assertFalse((self.root/'.skill-tree/invocations').exists())

    def test_explicit_disabled_configuration_requires_actual_current_dg_acceptance(self):
        self.install();self.core_review()
        before=self.read_publication()['review_requirements']['configuration_digest']
        self.disable();self.held()
        current=pr.review_requirement_plan(self.store,self.snapshot,
                                          package_root=self.package_root,run_overrides={})
        after=current['configuration']['configuration_digest']
        self.assertNotEqual(before,after)
        context=pr.review_configuration_context(self.snapshot,self.publication_id,before,after)
        decision=self.technical_decision(context)
        self.assertEqual(decision['acceptance']['answer'],'adopt')
        reconciled=self.cli('review-reconcile',decision_receipt={
            'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']})
        self.assertEqual(reconciled['review_requirements']['configuration_digest'],after)
        self.assertIn(decision['acceptance']['digest'],json.dumps(self.read_publication()),
                      'Adoption must persist the actual DG acceptance, not manufacture execution success.')
        self.assertFalse((self.root/'.skill-tree/invocations').exists())
        self.assertEqual(self.read_publication().get('hook_chains',[]),[])
        self.core_review()
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_explicit_uninstall_keeps_frozen_hold_until_real_dg_adopts_empty_configuration(self):
        self.install();self.core_review()
        before=self.read_publication()['review_requirements']['configuration_digest']
        self.uninstall();self.held()
        manifest=json.loads((self.package_root/'references/plugin-bindings.json').read_text())
        self.assertEqual(manifest['definitions'],[]);self.assertEqual(manifest['packages'],{})
        current=pr.review_requirement_plan(self.store,self.snapshot,package_root=self.package_root,
            run_overrides={},record=self.read_publication(),publication_id=self.publication_id)
        after=current['configuration']['configuration_digest'];self.assertNotEqual(before,after)
        decision=self.technical_decision(pr.review_configuration_context(
            self.snapshot,self.publication_id,before,after))
        adopted=self.cli('review-reconcile',decision_receipt={
            'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']})
        self.assertEqual(adopted['review_requirements']['configuration_digest'],after)
        self.assertFalse(any(adopted['review_requirements']['phases'].values()))
        self.assertEqual(adopted.get('hook_chains',[]),[])
        self.assertFalse((self.root/'.skill-tree/invocations').exists())
        self.core_review();self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_configuration_reconciliation_rejects_unknown_or_keep_decision(self):
        self.install();self.core_review()
        before=self.read_publication()['review_requirements']['configuration_digest']
        self.disable()
        retained=self.publication.read_bytes()
        self.cli('review-reconcile',ok=False,decision_receipt={
            'decision_id':'DG-00000000-0000-0000-0000-000000000001','acceptance_digest':'0'*64})
        self.assertEqual(self.publication.read_bytes(),retained)
        current=pr.review_requirement_plan(self.store,self.snapshot,
                                          package_root=self.package_root,run_overrides={})
        after=current['configuration']['configuration_digest']
        decision=self.technical_decision(pr.review_configuration_context(
            self.snapshot,self.publication_id,before,after),answer='keep')
        self.cli('review-reconcile',ok=False,decision_receipt={
            'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']})
        self.assertEqual(self.publication.read_bytes(),retained)
        self.held()

    def test_owned_descriptor_requires_bounded_original_source_and_immutable_policy(self):
        descriptor=json.loads((CORE/'config/plugins/ponytail.json').read_text())
        self.assertEqual(descriptor['source'],{'kind':'repository',
            'url':'https://github.com/DietrichGebert/ponytail','ref':PIN,'entry':ENTRY})
        self.assertEqual(descriptor['resources'],['LICENSE'])
        self.assertEqual(descriptor['dependencies'],[])
        self.assertEqual(descriptor['expectedDigests'],{ENTRY:ENTRY_SHA,'LICENSE':LICENSE_SHA})
        policy=descriptor['adapter']['invocation_policy']
        for key,value in POLICY.items():self.assertEqual(policy[key],value,key)
        self.assertTrue(policy['instructions'].strip(),'The owned boundary needs immutable adapter instructions.')
        self.assertEqual(descriptor['adapter']['parameter_defaults']['upstream']['values']['level'],'full')

    def test_actual_composed_resources_preserve_original_pin_and_license_bytes(self):
        self.install()
        m=json.loads((self.package_root/'references/plugin-bindings.json').read_text())
        self.assertEqual(m['packages']['ponytail']['revision'],PIN)
        self.assertEqual(m['packages']['ponytail']['content_digest'],
            '14147d26122fb21e825ff59f20d3eedd79ebdbf05c17eaae93daf67826ec5615')
        self.assertTrue(m['packages']['ponytail']['entry'].endswith('/'+ENTRY))
        copied=self.package_root/'plugins/ponytail/upstream'
        raw=(copied/ENTRY).read_bytes()
        self.assertEqual(len(raw),3496);self.assertEqual(hashlib.sha256(raw).hexdigest(),ENTRY_SHA)
        self.assertEqual(hashlib.sha1(b'blob 3496\0'+raw).hexdigest(),'d64edd32265ba21cbf5270158f04e97d96925f27')
        self.assertEqual(hashlib.sha256((copied/'LICENSE').read_bytes()).hexdigest(),LICENSE_SHA)
        self.assertFalse((copied/'skills/ponytail-review/SKILL.md').exists())

    def test_linked_worktree_freezes_execution_profile_and_routes_publication_to_canonical(self):
        self.install(selected=False)
        canonical=self.root.resolve();canonical_profile=canonical/'.skill-tree/installation/profile.json'
        self.publication=canonical/'.skill-tree/history/publications'/('pub-'+self.publication_id+'.json')
        unchanged=canonical_profile.read_bytes()
        subprocess.run(['git','-C',str(canonical),'add','--','package.json','source.py'],
                       check=True,capture_output=True)
        subprocess.run(['git','-C',str(canonical),'-c','user.name=Controlled Fixture',
                        '-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false',
                        '-c','core.hooksPath=/dev/null','commit','-q','-m','Fixture source only'],
                       check=True,capture_output=True)
        execution=(self.base/'linked-execution').resolve()
        subprocess.run(['git','-C',str(canonical),'-c','core.hooksPath=/dev/null',
                        'worktree','add','-q','-b','pilot-execution',str(execution)],
                       check=True,capture_output=True)
        locator=wf.workspaces.runtime_file(canonical)
        locator.write_text(json.dumps({'schema':1,'canonical_root':str(canonical),'worktrees':{}}))
        options={'selected':True,'enabled':True,'anchor':'after','flavor':'general',
                 'pin':PIN,'entry':ENTRY,'entry_sha':ENTRY_SHA,'license_sha':LICENSE_SHA,
                 'occurrence':OCCURRENCE,'instructions':'LINKED-EXECUTION','bindings':None}
        installed=subprocess.run(['node','-e',INSTALL,str(CORE),str(execution),str(RAW),json.dumps(options)],
                                 capture_output=True,text=True)
        self.assertEqual(installed.returncode,0,installed.stdout+installed.stderr)
        self.root=execution;self.package_root=Path(json.loads(installed.stdout)['package_root'])
        self.pr_script=self.package_root/'scripts/pr-review-state.py'
        self.store=wf.Store(execution,allow_unselected=True,neutral=True)
        self.assertEqual(self.store.root,canonical)
        self.assertEqual(self.store.source_root,execution)
        record=self.cli('init',merge=True,instruction='Synthetic linked-worktree PR cycle with merge.')
        execution_profile=(execution/'.skill-tree/installation/profile.json').read_bytes()
        self.assertEqual(record['review_requirements']['execution_snapshot']['owned-profile'],
                         hashlib.sha256(execution_profile).hexdigest())
        self.assertNotEqual(hashlib.sha256(execution_profile).hexdigest(),hashlib.sha256(unchanged).hexdigest())
        self.assertEqual(canonical_profile.read_bytes(),unchanged)
        # Core-only installation may represent the empty registry without a
        # registry file; ask the actual source verifier rather than invent one.
        inspected=subprocess.run(['node','-e',
            "process.stdout.write(JSON.stringify(require(process.argv[1]).verifyInstalled(process.argv[2])))",
            str(CORE/'lib/plugin-registry.js'),str(canonical)],capture_output=True,text=True)
        self.assertEqual(inspected.returncode,0,inspected.stdout+inspected.stderr)
        canonical_registry=json.loads(inspected.stdout)
        self.assertEqual(canonical_registry['packages'],{});self.assertEqual(canonical_registry['bindings'],[])
        self.assertEqual(self.publication.parent,canonical/'.skill-tree/history/publications')
        self.assertEqual(self.read_publication()['review_requirements'],record['review_requirements'])
        self.assertFalse((execution/'.skill-tree/history/publications').exists())
        for root in [canonical,execution]:
            self.assertFalse((root/'.skill-tree/documents/future.json').exists())
            self.assertFalse((root/'.skill-tree/documents/future.md').exists())
            self.assertFalse((root/'.skill-tree/invocations').exists())

    def test_actual_requirement_plan_is_read_only_and_cannot_authorize_business_start(self):
        self.install()
        def files():return {item.relative_to(self.root).as_posix():item.read_bytes()
                            for item in self.root.rglob('*') if item.is_file()}
        before=files();context=pr.hook_context(self.snapshot)
        event={'id':'metadata-requirement-observation','operation':OP,'anchor':'after'}
        plan=wf._hook_node(self.package_root,{'runtime_action':'requirement-plan',
            'project_root':str(self.root),'event':event,'context':context,
            'capabilities':self.capabilities,
            'adapter':{'provider':'codex','mechanism':'source-backed-context'}})
        self.assertEqual(plan['proof']['proof_kind'],'completed-readiness')
        self.assertEqual(files(),before,'Requirement observation cannot mutate installation or publication state.')
        self.assertFalse((self.root/'.skill-tree/invocations').exists())
        self.assertFalse((self.root/'.skill-tree/documents/future.json').exists())
        proof=plan['proof']
        payload={'request_id':'not-a-business-preparation','configuration':plan['configuration'],
            'event':proof['event'],'context':proof['context'],'mode':'manual',
            'authority':{'id':'synthetic-requirement-grant','revision':1,'context_id':proof['context']['id'],
                'allowed_kinds':['technical'],'constraints':['Synthetic temporary metadata only.'],
                'evidence':{'kind':'owner-message','reference':'Unit fixture, not actual owner approval.'}},
            'executor':{'id':'metadata-executor','context_id':'metadata-executor-context'}}
        with self.assertRaisesRegex(ValueError,r'(?i)readiness|business'):
            engine().start(self.store,payload,proof=proof)
        self.assertEqual(files(),before)

    def test_missing_publication_identity_rejects_pilot_before_activation(self):
        self.install(anchor='after')
        before=self.publication.read_bytes()
        with self.assertRaisesRegex(ValueError,r'(?i)publication|phase|core|review'):
            self.start(publication_bound=False)
        self.assertFalse((self.root/'.skill-tree/invocations').exists(),
                         'A selected review pilot cannot activate an unbound pass before phase authority.')
        self.assertEqual(self.publication.read_bytes(),before)
        self.assertNotIn('hook_chains',self.read_publication())

    def test_owned_custom_named_after_alias_completes_and_satisfies_readiness(self):
        controlled=self.base/'custom-alias-source';alias='fixture-quality-report'
        stage=r"""const fs=require('node:fs'),path=require('node:path');
const source=process.argv[1],target=process.argv[2],operation=process.argv[3],alias=process.argv[4];
const composer=require(path.join(source,'lib/composer.js'));
fs.mkdirSync(target);
for(const relative of Object.keys(composer.sourceInputs(source))){
 const destination=path.join(target,relative);fs.mkdirSync(path.dirname(destination),{recursive:true});
 fs.copyFileSync(path.join(source,relative),destination);
}
const file=path.join(target,'templates/operations.json'),operations=JSON.parse(fs.readFileSync(file,'utf8'));
operations[operation].plugin_anchors={...(operations[operation].plugin_anchors||{}),[alias]:'after'};
fs.writeFileSync(file,JSON.stringify(operations,null,2)+'\n');"""
        staged=subprocess.run(['node','-e',stage,str(CORE),str(controlled),OP,alias],capture_output=True,text=True)
        self.assertEqual(staged.returncode,0,staged.stdout+staged.stderr)
        self.assertEqual((controlled/'config/plugins/ponytail.json').read_bytes(),
                         (CORE/'config/plugins/ponytail.json').read_bytes())
        self.install(anchor=alias,source=controlled);self.core_review()
        frame=self.complete(self.start(request_id='owned-custom-alias'))
        self.assertEqual(frame['event']['anchor'],alias)
        self.assertEqual(frame['event']['boundary_id'],OP+':after')
        self.assertEqual(frame['stages'][0]['status'],'complete')
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_after_entry_rejects_unresolved_core_report_and_needs_clean_current_pass(self):
        self.install()
        finding={'id':'CORE-NEEDS-SUBSTANTIATION','path':'source.py','line':2,
            'cause':'The fixture default value is alleged to be wrong.',
            'consequence':'A consumer is alleged to receive an invalid default.','severity':'P1'}
        self.core_review([finding]);source=(self.root/'source.py').read_bytes();head=self.snapshot['head']
        self.assertEqual(self.read_publication()['review']['unresolved'],1)
        with self.assertRaisesRegex(ValueError,r'(?i)unresolved|finding|core|review|clean'):
            self.start(request_id='premature-after-core-finding')
        self.assertFalse((self.root/'.skill-tree/invocations').exists())
        check="from pathlib import Path; ns={}; exec(Path('source.py').read_text(),ns); assert ns['value']()==1"
        verified=subprocess.run(['python3','-I','-B','-c',check],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(verified.returncode,0,verified.stdout+verified.stderr)
        dismissed={**finding,'status':'dismissed','verified_head':head,
            'dismissal_reason':'The fixture contract expects one; the independent current-source assertion confirms one.',
            'verification_evidence':['Independent fixture value()==1 assertion passed for the unchanged current source.']}
        self.core_review([dismissed]);self.held()
        self.assertEqual(self.snapshot['head'],head);self.assertEqual((self.root/'source.py').read_bytes(),source)
        self.complete(self.start(request_id='clean-after-evidence-dismissal'))
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_current_after_pass_requires_full_core_review_before_start(self):
        self.install(anchor='after')
        with self.assertRaisesRegex(ValueError,r'(?i)core|review|phase|inspection|publication'):
            self.start()

    def test_during_cannot_start_before_first_full_core_inspection(self):
        self.install(anchor='during')
        with self.assertRaisesRegex(ValueError,r'(?i)core|review|phase|inspection|publication'):
            self.start()

    def test_during_runs_after_actual_inspection_and_still_requires_final_full_review(self):
        self.install(anchor='during');self.core_inspection()
        self.assertNotIn('review',self.read_publication(),
                         'The inspection checkpoint cannot masquerade as final full review.')
        self.complete(self.start())
        self.held()
        self.core_review()
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_before_pass_cannot_replace_complete_core_review(self):
        self.install(anchor='before');self.complete(self.start())
        self.held();self.core_review();self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_before_chain_skipping_after_stage_cannot_satisfy_after_obligation(self):
        occurrences=[{'id':'pilot-before','plugin_id':'ponytail','operation':OP,
                      'anchor':'before','enabled':True},
                     {'id':'pilot-after','plugin_id':'ponytail','operation':OP,
                      'anchor':'after','enabled':True}]
        self.install(anchor='before',bindings=occurrences)
        before=self.complete(self.start(request_id='actual-before-phase'))
        stages={stage['binding_id']:stage['status'] for stage in before['stages']}
        self.assertEqual(stages,{'pilot-before':'complete','pilot-after':'skipped'})
        self.assertEqual({attempt['binding_id'] for attempt in before['attempts'].values()},{'pilot-before'})
        self.core_review();self.held()
        self.anchor='after'
        after=self.complete(self.start(request_id='actual-after-phase'))
        self.assertNotEqual(before['id'],after['id'])
        self.assertEqual({attempt['binding_id'] for attempt in after['attempts'].values()},{'pilot-after'})
        self.assertEqual(self.read_publication()['hook_chains'],[before['id'],after['id']])
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_after_completed_but_unattached_chain_is_not_inferred_as_publication_evidence(self):
        self.install();self.core_review();frame=self.complete(self.start(),attach=False)
        self.assertEqual(engine().read(self.store,frame['id'])['state'],'complete')
        self.assertNotIn('hook_chains',self.read_publication())
        self.held()

    def test_explicit_current_attached_completion_allows_ready_without_external_approval(self):
        self.install();self.core_review();self.complete(self.start())
        ready=self.cli('ready');self.assertEqual(ready['status'],'pr-ready')
        self.assertFalse(ready['review']['independent_approval'])

    def test_actual_private_dispatch_keeps_immutable_policy_when_extra_instructions_replace(self):
        override={OCCURRENCE:{'instructions':'RUN-REPLACES-ORDINARY-EXTRA',
            'values':{'invocation_policy':{'kind':'unbounded','require_context_end':False},
                      'mode':'invented-plugin-mode','authority':{'merge':True}}}}
        self.install(instructions='BINDING-REPLACES-ORDINARY-EXTRA',run_overrides=override);self.core_review()
        frame=self.start(run_overrides=override);observed=[]
        frame,_=self.returned(frame,capture=observed)
        self.assertEqual(len(observed),1)
        delivery=observed[0]
        self.assertEqual(delivery['extra_instructions'],'RUN-REPLACES-ORDINARY-EXTRA')
        self.assertEqual(delivery['invocation_policy'],self.pilot_policy)
        self.assertEqual(delivery['mode'],'manual')
        self.assertNotIn('merge',delivery['authority'])
        self.assertEqual(delivery['allowed_actions'],['return-proposals'])
        self.assertEqual(delivery['parameters']['invocation_policy']['require_context_end'],False,
            'Ordinary arbitrary parameter data stays data rather than replacing policy.')
        self.assertEqual(self.attempt(frame)['input']['invocation_policy'],self.pilot_policy)

    def test_trusted_private_provider_cannot_remove_or_alter_sealed_policy_before_sink(self):
        self.install();self.core_review();frame=self.prepare(self.start())
        attempt=self.attempt(frame);delivery=self.private_delivery(frame)
        headers={key:delivery[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']}
        payload={'chain_id':frame['id'],'expected_chain_hash':frame['chain_hash'],
            'expected_chain_revision':frame['revision'],'attempt_id':attempt['id'],**headers,
            'evidence':{'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-private-dispatch',
                'reference':'Synthetic trusted-provider tamper control; no native actor.',
                'actor_id':attempt['actor']['id'],'actor_context_id':attempt['actor']['context_id'],
                'mechanism':'source-backed-context'}}
        carrier=engine().location(self.store,frame['id']);original=carrier.read_bytes()
        observed=[];calls=[]
        for field in ['invocation_policy','allowed_tools','allowed_actions']:
            for mutation in ['remove','alter']:
                with self.subTest(field=field,mutation=mutation):
                    def provider(request):
                        self.assertFalse((self.store.base/'.writer-lock').exists())
                        envelope=wf._hook_node(Path(request['package_root']),request)
                        self.assertEqual(envelope['payload']['invocation_policy'],self.pilot_policy)
                        calls.append((field,mutation))
                        if mutation=='remove':envelope['payload'].pop(field)
                        elif field=='invocation_policy':envelope['payload'][field]['require_context_end']=False
                        else:envelope['payload'][field]=['write-project' if field=='allowed_tools' else 'merge']
                        return envelope
                    with self.assertRaisesRegex(ValueError,r'(?i)policy|tools|actions|sealed'):
                        wf.hook_action(self.store,'hook-invoke',payload,
                                       private_delivery_provider=provider,private_delivery_sink=observed.append)
                    self.assertEqual(observed,[],'A tampered private envelope cannot reach the dispatch sink.')
                    self.assertEqual(carrier.read_bytes(),original,'Rejected delivery cannot mutate original attempt bytes.')
                    self.assertEqual(engine().read(self.store,frame['id']),frame)
        self.assertEqual(len(calls),6)

    def test_empty_run_instructions_cannot_remove_immutable_review_policy(self):
        override={OCCURRENCE:{'instructions':''}}
        self.install(run_overrides=override);self.core_review()
        frame=self.start(run_overrides=override)
        frame=self.prepare(frame);private=self.private_delivery(frame)
        self.assertEqual(private['payload']['extra_instructions'],'')
        self.assertEqual(private['payload']['invocation_policy'],self.pilot_policy)

    def test_actor_identity_or_executor_context_reuse_is_rejected(self):
        self.install();self.core_review();frame=self.start()
        for actor in [{'id':'pilot-executor','context_id':'fresh-context'},
                      {'id':'fresh-actor','context_id':'pilot-executor-context'}]:
            before=engine().read(self.store,frame['id'])
            with self.assertRaisesRegex(ValueError,r'(?i)isolated|actor|context'):
                self.prepare(frame,actor)
            self.assertEqual(engine().read(self.store,frame['id']),before)

    def test_retry_requires_fresh_actor_and_context_for_the_same_occurrence(self):
        self.install();self.core_review();frame,_=self.returned(self.start(),'failed')
        original=copy.deepcopy(self.attempt(frame))
        frame=self.change(frame,'resume',retry=True,
                          reason='A separately recorded failed original attempt needs a fresh isolated retry.')
        for actor in [original['actor'],
                      {'id':'fresh-retry-actor','context_id':original['actor']['context_id']},
                      {'id':original['actor']['id'],'context_id':'fresh-retry-context'}]:
            before=engine().read(self.store,frame['id'])
            with self.assertRaisesRegex(ValueError,r'(?i)fresh|isolated|actor|context'):
                self.prepare(frame,actor)
            self.assertEqual(engine().read(self.store,frame['id']),before)
        current=self.prepare(frame,{'id':'fresh-retry-actor','context_id':'fresh-retry-context'})
        self.assertNotEqual(self.attempt(current)['id'],original['id'])
        self.assertEqual(current['attempts'][original['id']],original)

    def test_report_result_cannot_extend_session_mode_into_parent(self):
        for claim in ['parent_mode','activate_session','session_active']:
            self.install();self.core_review()
            with self.assertRaisesRegex(ValueError,r'(?i)report|session|parent|mode'):
                self.returned(self.start(),result_extra={claim:True})
            self.held()

    def test_missing_or_actor_claimed_context_end_cannot_complete(self):
        for end in [None,{'kind':'actor-self-report','state':'ended'}]:
            self.install();self.core_review();frame=self.start()
            with self.assertRaisesRegex(ValueError,r'(?i)context|host|end|lifetime|cleanup'):
                self.complete(frame,end=end)
            self.held()

    def test_actor_result_context_end_claim_cannot_replace_producer_evidence(self):
        self.install();self.core_review();frame=self.prepare(self.start())
        frame,delivery=self.invoke(frame);attempt=self.attempt(frame)
        result={'status':'passed','context_end_evidence':self.context_end(frame)}
        evidence={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
            'reference':'Synthetic result body copies a cleanup claim; no producer cleanup accompanies it.',
            'actor_id':attempt['actor']['id'],'actor_context_id':attempt['actor']['context_id'],
            'mechanism':'source-backed-context'}
        with self.assertRaisesRegex(ValueError,r'(?i)context|host|end|cleanup'):
            self.change(frame,'record',attempt_id=attempt['id'],
                **{key:delivery[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']},
                result=result,evidence=evidence)
        self.held()

    def test_wrong_actor_context_attempt_or_delivery_end_cannot_complete(self):
        for field in ['actor_id','actor_context_id','attempt_id','input_digest','delivery_digest','provider','state']:
            self.install();self.core_review();frame=self.prepare(self.start())
            frame,delivery=self.invoke(frame);bad=self.context_end(frame);bad[field]='foreign'
            a=self.attempt(frame)
            evidence={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
                'reference':'Synthetic result with deliberately mismatched cleanup.',
                'actor_id':a['actor']['id'],'actor_context_id':a['actor']['context_id'],'mechanism':'source-backed-context'}
            with self.assertRaisesRegex(ValueError,r'(?i)context|host|end|lifetime|cleanup|identity|digest'):
                returned=self.change(frame,'record',attempt_id=a['id'],
                    **{k:delivery[k] for k in ['input_digest','delivery_digest','resolved_parameter_digest']},
                    result={'status':'passed'},evidence=evidence,context_end_evidence=bad)
                self.accept(returned,end=bad)
            self.held()

    def test_failed_unavailable_cancelled_or_unknown_attempt_never_reaches_ready(self):
        for status in ['failed','unavailable','cancelled']:
            self.install();self.core_review();returned,_=self.returned(self.start(),status)
            self.held()
            with self.assertRaises(ValueError):self.accept(returned)
        self.install();self.core_review();frame=self.prepare(self.start());frame,_=self.invoke(frame)
        a=self.attempt(frame)
        self.change(frame,'reconcile',attempt_id=a['id'],status='unknown',
            evidence={'kind':'host-reconciliation','reference':'Synthetic uncertain original transport.'})
        self.held()

    def test_missing_host_capability_cannot_be_silently_skipped(self):
        self.install();self.core_review();self.capabilities=[]
        frame=self.start();next_action=wf.hook_action(self.store,'hook-next',{'chain_id':frame['id']})
        self.assertEqual(next_action['action'],'prerequisite');self.held()

    def test_missing_resource_or_configuration_drift_holds_current_publication(self):
        for kind in ['resource','configuration']:
            self.install();self.core_review();self.complete(self.start())
            if kind=='resource':(self.package_root/'plugins/ponytail/upstream/LICENSE').unlink()
            else:
                path=self.root/'.skill-tree/installation/plugins.json'
                value=json.loads(path.read_text());value['bindings'][0]['instructions']='Changed after accepted result'
                path.write_text(json.dumps(value))
            self.held()

    def test_current_head_base_target_changes_invalidate_previously_completed_pass(self):
        for field,value in [('head','c'*40),('base_oid','e'*40),('target_branch','release/fixture')]:
            self.install();self.core_review();self.complete(self.start())
            self.snapshot[field]=value
            if field=='target_branch':
                self.cli('observe',ok=False)
                changed=self.cli('init',target_branch=value,instruction='Synthetic owner explicitly retargets the existing publication.')
                self.assertFalse(changed['authorization']['merge'])
                self.assertEqual(changed['authorization_history'][-1]['target_branch'],'develop')
            else:
                self.cli('observe')
            self.core_review();self.held()

    def test_findings_cannot_be_accepted_without_current_core_resolution(self):
        self.install();self.core_review();returned,_=self.returned(self.start(),'findings',
            result_extra={'findings':[{'id':'PILOT-1','path':'source.py','line':2,
                'cause':'A caller loses the existing validation.','consequence':'Invalid input reaches the operation.','severity':'P1'}]})
        with self.assertRaisesRegex(ValueError,r'(?i)resolution|incorporation|transition|decision'):
            self.accept(returned)
        self.held()

    def test_actual_generic_dg_resolution_cannot_bypass_review_finding_incorporation(self):
        self.install();self.core_review()
        finding={'id':'UNRESOLVED-PILOT-ONE','path':'source.py','line':2,
            'cause':'The fixture returns an allegedly invalid constant.',
            'consequence':'The alleged defect remains for ordinary review and a future fix.','severity':'P1'}
        chain,_=self.returned(self.start(request_id='generic-resolution-control'),'findings',
                              result_extra={'findings':[finding]})
        attempt=self.attempt(chain);decision=self.generic_resolution_decision(chain,attempt)
        self.assertEqual(decision['authority'],chain['authority'])
        self.assertEqual(decision['mode'],chain['mode']);self.assertEqual(decision['executor'],chain['executor'])
        reference={'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']}
        identity=engine().digest(chain['context']);original=engine().location(self.store,chain['id']).read_bytes()
        receipt={'kind':'core-resolution','before':identity,'after':identity,'decision_receipt':reference,
                 'reference':'Real accepted synthetic DG substantiation; no publication incorporation or resolution.'}
        with self.assertRaisesRegex(ValueError,r'(?i)finding|review|publication|incorporat|contribution'):
            self.accept(chain,receipt=receipt)
        self.assertEqual(engine().location(self.store,chain['id']).read_bytes(),original)
        self.assertEqual(self.read_publication().get('findings',{}),{})
        self.assertEqual(self.read_publication().get('review_plugin_contributions',{}),{})
        self.held()

    def test_plugin_false_positive_dismissal_preserves_accepted_pass_without_input_change(self):
        self.install();self.core_review();head=self.snapshot['head'];source=(self.root/'source.py').read_bytes()
        finding={'id':'FALSE-POSITIVE','path':'source.py','line':2,
            'cause':'The fixture constant is alleged to violate its default contract.',
            'consequence':'The fixture consumer is alleged to receive a wrong value.','severity':'P1'}
        chain,_=self.returned(self.start(request_id='false-positive-review'),'findings',
                              result_extra={'findings':[finding]})
        attempt=self.attempt(chain)
        context=pr.review_findings_context(self.snapshot,self.publication_id,chain['id'],
                                          attempt['id'],engine().digest(attempt['result']))
        decision=self.technical_decision(context,answer='incorporate',findings=True)
        contribution=self.cli('plugin-findings',chain_id=chain['id'],attempt_id=attempt['id'],
            decision_receipt={'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']})
        chain=self.accept(chain,receipt=contribution['contribution_receipt'])
        self.cli('hook-attach',chain_id=chain['id']);self.held()
        self.assertEqual(len(contribution['findings']),1);identity,tracked=next(iter(contribution['findings'].items()))
        check="from pathlib import Path; ns={}; exec(Path('source.py').read_text(),ns); assert ns['value']()==1"
        verified=subprocess.run(['python3','-I','-B','-c',check],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(verified.returncode,0,verified.stdout+verified.stderr)
        dismissed={**tracked,'status':'dismissed','verified_head':head,
            'dismissal_reason':'The current fixture contract expects one and the independent source assertion confirms one.',
            'verification_evidence':['Independent current-source fixture value()==1 assertion passed; no code change required.']}
        invocation_root=self.store.base/'invocations'
        accepted_files={item.relative_to(invocation_root).as_posix():item.read_bytes()
                        for item in invocation_root.rglob('*') if item.is_file()}
        self.core_review([dismissed])
        self.assertEqual(self.read_publication()['findings'][identity]['status'],'dismissed')
        self.assertEqual(self.snapshot['head'],head);self.assertEqual((self.root/'source.py').read_bytes(),source)
        self.assertEqual(self.read_publication()['hook_chains'],[chain['id']])
        self.assertEqual(self.cli('ready')['status'],'pr-ready')
        self.assertEqual({item.relative_to(invocation_root).as_posix():item.read_bytes()
                          for item in invocation_root.rglob('*') if item.is_file()},accepted_files,
                         'Dismissing the accepted pass own false positive cannot require or create a replay when inputs stay current.')

    def test_actual_plugin_finding_enters_core_ledger_and_needs_fix_checks_review_and_fresh_pilot(self):
        self.install();self.core_review()
        finding={'id':'PLUGIN-ONE','path':'source.py','line':2,
            'cause':'The fixture returns the old constant.',
            'consequence':'The required fixture value is wrong.','severity':'P1'}
        frame,_=self.returned(self.start(),'findings',result_extra={'findings':[finding]})
        attempt=self.attempt(frame);original_review=copy.deepcopy(self.read_publication()['review'])
        original_rounds=copy.deepcopy(self.read_publication()['rounds'])
        # Acknowledgement alone cannot invent an ordinary core incorporation.
        unchanged=engine().read(self.store,frame['id']);context=frame['context']
        with self.assertRaisesRegex(ValueError,r'(?i)contribution|publication|incorporation|receipt|core'):
            self.accept(frame,receipt={'kind':'core-incorporation','publication_id':self.publication_id,
                'contribution_id':'fabricated-acknowledgement','reference':'Synthetic acknowledgement without a core action.',
                'before':engine().digest(context),'after':engine().digest(context)})
        self.assertEqual(engine().read(self.store,frame['id']),unchanged)
        decision_context=pr.review_findings_context(self.snapshot,self.publication_id,
            frame['id'],attempt['id'],engine().digest(attempt['result']))
        decision=self.technical_decision(decision_context,answer='incorporate',findings=True)
        contribution=self.cli('plugin-findings',chain_id=frame['id'],attempt_id=attempt['id'],
            decision_receipt={'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']})
        ledger=contribution['findings'];self.assertEqual(len(ledger),1)
        identity,tracked=next(iter(ledger.items()))
        self.assertNotEqual(identity,finding['id'],'External IDs require a contribution namespace.')
        for key in ['path','line','cause','consequence','severity']:self.assertEqual(tracked[key],finding[key])
        self.assertEqual(contribution['review'],original_review)
        self.assertEqual(contribution['rounds'],original_rounds)
        frame=self.accept(frame,receipt=contribution['contribution_receipt'])
        self.cli('hook-attach',chain_id=frame['id'])
        self.core_review();self.held()
        self.assertEqual(self.read_publication()['findings'][identity].get('status','open'),'open')
        # Verify an independent functional fixture regression before and after the fix.
        regression="from pathlib import Path; ns={}; exec(Path('source.py').read_text(),ns); assert ns['value']()==2"
        failing=subprocess.run(['python3','-I','-B','-c',regression],cwd=self.root,capture_output=True,text=True)
        self.assertNotEqual(failing.returncode,0)
        (self.root/'source.py').write_text('def value():\n    return 2\n')
        self.snapshot['head']='f'*40
        self.snapshot['checks'][0]['status']='pending'
        self.cli('observe');self.held()
        passed=subprocess.run(['python3','-I','-B','-c',regression],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(passed.returncode,0,passed.stdout+passed.stderr)
        self.snapshot['checks'][0]['status']='success'
        fixed={**tracked,'status':'verified-fixed','verified_head':self.snapshot['head'],
               'verification_evidence':['Independent fixture regression value()==2 failed before fix and passed after fix.']}
        self.core_review([fixed]);self.held()
        self.complete(self.start(request_id='fresh-post-fix-pilot'))
        self.assertEqual(self.cli('ready')['status'],'pr-ready')

    def test_fixed_finding_requires_new_head_full_review_and_current_pilot(self):
        self.install();self.core_review();self.complete(self.start())
        finding={'id':'CORE-1','path':'source.py','line':2,'cause':'The caller uses old state.',
                 'consequence':'The operation returns wrong data.','severity':'P1'}
        self.core_review([finding]);self.held()
        self.snapshot['head']='f'*40
        fixed={**finding,'status':'verified-fixed','verified_head':self.snapshot['head'],
               'verification_evidence':['Independent scripted regression assertion.']}
        self.core_review([fixed]);self.held()

    def test_plugin_cannot_satisfy_external_approval_or_owner_merge_authority(self):
        self.install();self.core_review();original=self.complete(self.start())
        self.snapshot.update({'approvals_required':True,'approved':False})
        # Review identity changes: refresh ordinary review, but stale plugin remains held too.
        self.core_review();self.held()
        self.snapshot.update({'approvals_required':False,'approved':True})
        self.core_review()
        # Restoring provider identity retains archived history but does not
        # implicitly restore active references. Explicitly reattach the current pass.
        self.held()
        archived=copy.deepcopy(self.read_publication().get('review_hook_history',[]))
        self.assertNotIn(original['id'],self.read_publication().get('hook_chains',[]))
        self.assertIn(original['id'],json.dumps(archived))
        self.cli('hook-attach',chain_id=original['id'])
        self.assertEqual(self.read_publication().get('review_hook_history',[]),archived)
        self.assertEqual(self.cli('ready')['status'],'pr-ready')
        self.snapshot.update({'approvals_required':True,'approved':False})
        # Direct core merge gate oracle independently rejects external approval even with a clean core record.
        record=pr.reviewed(pr.new_record(self.snapshot,pr.parameters('feature/pilot-fixture',{'merge':True})),
            self.snapshot,{'head':self.snapshot['head'],'base_oid':self.snapshot['base_oid'],
            'target_branch':self.snapshot['target_branch'],'files':['source.py'],'context_inspected':True,
            'discussions_inspected':True,'checks_inspected':True,'findings':[]})
        with self.assertRaisesRegex(pr.ReviewError,'External approval'):
            pr.merge_gate(record,self.snapshot)
        self.snapshot.update({'approvals_required':False,'approved':True})
        record['authorization']['merge']=False
        with self.assertRaisesRegex(pr.ReviewError,'Merge lacks'):
            pr.merge_gate(pr.reviewed(record,self.snapshot,{'head':self.snapshot['head'],
                'base_oid':self.snapshot['base_oid'],'target_branch':self.snapshot['target_branch'],
                'files':['source.py'],'context_inspected':True,'discussions_inspected':True,
                'checks_inspected':True,'findings':[]}),self.snapshot)

    def test_policy_bound_review_rejects_contradictory_success_payloads_at_record(self):
        finding={'id':'CONCRETE-REPORT-FINDING','path':'source.py','line':2,
            'cause':'The fixture returns an alleged invalid default.',
            'consequence':'The alleged contract violation remains for ordinary core substantiation.',
            'severity':'P1'}
        question={'id':'REVIEW-QUESTION','text':'Which explicit fixture default is required?',
                  'options':[{'id':'one','text':'The existing default one.'},
                             {'id':'two','text':'The proposed default two.'}]}
        cases=[('passed',{'findings':[finding]}),
               ('questions',{'findings':[finding]}),
               ('passed',{'questions':[question]}),
               ('findings',{'questions':[question]})]
        for status,payload in cases:
            with self.subTest(status=status,payload=payload):
                self.install();self.core_review();chain=self.start()
                self.assertEqual(chain['configuration']['packages']['ponytail']['adaptation']
                                 ['invocation_policy']['kind'],'report-only')
                # returned() performs actual owned prepare/invoke/record, supplies
                # matching producer context-end evidence, and captures no invented
                # receipt. Rejection must occur at record, before no-change accept.
                with self.assertRaisesRegex(ValueError,r'(?i)finding|question|status|outcome|conflict|report'):
                    self.returned(chain,status,result_extra=payload)
                current=engine().read(self.store,chain['id']);attempt=self.attempt(current)
                self.assertEqual(attempt['status'],'invoking')
                self.assertIsNone(attempt['result'])
                self.assertEqual(self.read_publication().get('findings',{}),{})
                self.assertEqual(self.read_publication().get('review_plugin_contributions',{}),{})
                self.held()

    def test_policy_bound_review_preserves_empty_reserved_arrays_and_arbitrary_annotations(self):
        self.install();self.core_review()
        payload={'findings':[],'questions':[],
                 'notes':['No actionable findings in the inspected fixture.',{'language':'русский','count':2}],
                 'custom':{'nested':[None,True,3,{'status':'annotation-only','findings':['ordinary nested data']}],
                           'opaque':{'questions':{'free':'ordinary nested annotation'}}}}
        chain,ended=self.returned(self.start(),'passed',result_extra=payload)
        attempt=self.attempt(chain)
        self.assertEqual(attempt['input']['invocation_policy']['kind'],'report-only')
        self.assertEqual(attempt['result'],{'status':'passed',**payload})
        chain=self.accept(chain,end=ended)
        self.cli('hook-attach',chain_id=chain['id'])
        self.assertEqual(self.cli('ready')['status'],'pr-ready')
        self.assertEqual(self.read_publication().get('findings',{}),{})

if __name__=='__main__':unittest.main()
