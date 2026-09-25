import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { adminViewHref, useAdminNavigation } from '../../src/companyAdmin/navigation'

afterEach(()=>{cleanup();window.history.replaceState(null,'','#/admin-companies')})

function NavigationProbe() {
  const nav=useAdminNavigation()
  const section=nav.choice('section',['overview','research','audit'] as const,'overview')
  return <><output>{section}:{nav.params.get('source')}</output>
    <a href={nav.href({section:'audit'})} aria-current={section==='audit'?'page':undefined}>Audit</a>
    <button onClick={()=>nav.update({section:'research',source:'firm 1'})}>Edit identity</button>
  </>
}

test('company deep links retain encoded account, source identity and section',()=>{
  expect(adminViewHref('#/admin-company/account%201?section=research&source=firm%2F1',{section:'audit'}))
    .toBe('#/admin-company/account%201?section=audit&source=firm%2F1')
  expect(adminViewHref('#/admin-companies?q=Water&page=3',{q:null,page:null,hierarchy:'parents'}))
    .toBe('#/admin-companies?hierarchy=parents')
})

test('direct links, same-page navigation and history changes select the linked view',()=>{
  window.history.replaceState(null,'','#/admin-company/account?section=audit&source=firm%2F1')
  render(<NavigationProbe/>)
  expect(screen.getByRole('status')).toHaveTextContent('audit:firm/1')
  expect(screen.getByRole('link',{name:'Audit'})).toHaveAttribute('aria-current','page')
  fireEvent.click(screen.getByRole('button',{name:'Edit identity'}))
  expect(window.location.hash).toContain('section=research&source=firm+1')
  expect(screen.getByRole('status')).toHaveTextContent('research:firm 1')
  act(()=>{window.history.replaceState(null,'','#/admin-company/another?section=overview');window.dispatchEvent(new HashChangeEvent('hashchange'))})
  expect(screen.getByRole('status')).toHaveTextContent('overview:')
})

test('invalid linked sections fall back to a usable overview',()=>{
  window.history.replaceState(null,'','#/admin-company/account?section=missing')
  render(<NavigationProbe/>)
  expect(screen.getByRole('status')).toHaveTextContent('overview:')
})
