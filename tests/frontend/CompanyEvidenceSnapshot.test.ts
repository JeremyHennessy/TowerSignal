import { beforeEach, expect, test, vi } from 'vitest'
const mocks=vi.hoisted(()=>({rpc:vi.fn(),config:null as null|{dataApi:{options:{global:{fetch:typeof fetch}}}}}))
vi.mock('@neondatabase/neon-js',()=>({createClient:(config:NonNullable<typeof mocks.config>)=>{mocks.config=config;return {rpc:mocks.rpc}}}))
import { loadCompanyEvidence } from '../../src/companyAdmin/client'

beforeEach(()=>vi.clearAllMocks())
test('saved parent and confirmed link are read in one complete snapshot',async()=>{
  const evidence={parents:[{parent_entity_id:'p',display_name:'Reviewed Parent'}],relationships:[{parent_entity_id:'p',status:'confirmed'}],sources:[],runs:[],candidates:[]}
  mocks.rpc.mockResolvedValue({data:evidence,error:null})
  expect(await loadCompanyEvidence()).toEqual(evidence)
  expect(mocks.rpc).toHaveBeenCalledWith('towersignal_company_evidence_snapshot')
})
test('missing evidence arrays and API errors cannot become empty successful results',async()=>{
  mocks.rpc.mockResolvedValueOnce({data:{parents:[]},error:null}).mockResolvedValueOnce({data:null,error:{message:'permission denied'}})
  await expect(loadCompanyEvidence()).rejects.toThrow('incomplete snapshot')
  await expect(loadCompanyEvidence()).rejects.toThrow('permission denied')
})
test('private requests bypass browser cache while preserving method and headers',async()=>{
  const fetchMock=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('[]'))
  try{
    await mocks.config!.dataApi.options.global.fetch('https://example.com/private',{method:'GET',headers:{'X-Test':'preserved'}})
    expect(fetchMock).toHaveBeenCalledWith('https://example.com/private',{method:'GET',headers:{'X-Test':'preserved'},cache:'no-store'})
  }finally{fetchMock.mockRestore()}
})

test('administrator access requires an explicit server boolean; missing results never become a false role',async()=>{
  vi.stubEnv('MODE','production')
  vi.resetModules()
  try{
    const {loadCompanyAdminAccess}=await import('../../src/companyAdmin/client')
    mocks.rpc.mockResolvedValue({data:true,error:null})
    await expect(loadCompanyAdminAccess()).resolves.toBe(true)
    mocks.rpc.mockResolvedValue({data:false,error:null})
    await expect(loadCompanyAdminAccess()).resolves.toBe(false)
    mocks.rpc.mockResolvedValue({data:null,error:null})
    await expect(loadCompanyAdminAccess()).rejects.toThrow('verification returned no result')
    expect(mocks.rpc).toHaveBeenCalledWith('towersignal_is_admin')
  }finally{vi.unstubAllEnvs()}
})
