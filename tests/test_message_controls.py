"""Message control regressions without requiring a HA server."""
import asyncio
from types import SimpleNamespace
import unittest
from test_transport_compat import load_definitions

class Base:
 def __init__(self, coordinator, *args): self.coordinator=coordinator
 @property
 def available(self): return self.coordinator.available

class MessageTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.calls=[]
  async def send(command, values):
   self.calls.append((command,values));return {'success':self.success,'message':'rejected'}
  self.success=True
  self.data=SimpleNamespace(values={'message_text':'hello','message_sound':False,'message_supported':True},available=True,_async_send_command=send)
  self.ns=dict(CompanionLinkEntity=Base,TextEntity=type('TextEntity',(),{}),ButtonEntity=type('ButtonEntity',(),{}),SwitchEntity=type('SwitchEntity',(),{}),TextMode=SimpleNamespace(TEXT='text'),HomeAssistantError=ValueError)
  for file,name in [('text.py','CompanionLinkMessageText'),('button.py','CompanionLinkSendMessageButton'),('switch.py','CompanionLinkMessageSound')]:
   load_definitions(file,self.ns,{name})
 async def test_draft_and_sound_only_save_configuration(self):
  text=self.ns['CompanionLinkMessageText'](self.data)
  sound=self.ns['CompanionLinkMessageSound'](self.data)
  self.assertEqual(text.native_value,'hello');self.assertFalse(sound.is_on)
  await text.async_set_value('明天见\n早点休息')
  await sound.async_turn_on();await sound.async_turn_off()
  self.assertEqual(self.calls,[('set_message_config',{'text':'明天见\n早点休息'}),('set_message_config',{'play_sound':True}),('set_message_config',{'play_sound':False})])
 async def test_send_button_uses_saved_draft_and_reports_device_errors(self):
  button=self.ns['CompanionLinkSendMessageButton'](self.data)
  await button.async_press();self.assertEqual(self.calls,[('send_message',{})])
  self.success=False
  with self.assertRaisesRegex(ValueError,'rejected'): await button.async_press()
  with self.assertRaisesRegex(ValueError,'rejected'): await self.ns['CompanionLinkMessageText'](self.data).async_set_value('bad')
 async def test_message_controls_discovered_once_after_capability_appears(self):
  # Load the small discovery helper directly, retaining real listener behavior.
  import ast
  from test_transport_compat import SOURCE
  tree=ast.parse((SOURCE/'entity.py').read_text(encoding='utf-8-sig'))
  node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='add_message_entities')
  ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'entity.py','exec'),ns)
  listeners=[];unloads=[];entities=[]
  self.data.values={};self.data.add_listener=lambda fn:(listeners.append(fn) or (lambda:None))
  entry=SimpleNamespace(async_on_unload=unloads.append)
  ns['add_message_entities'](entry,self.data,entities.extend,lambda d:['text','sound','send'])
  self.assertEqual(entities,[])
  self.data.values['message_supported']=True
  listeners[0]();listeners[0]()
  self.assertEqual(entities,['text','sound','send']);self.assertEqual(len(unloads),1)

if __name__=='__main__': unittest.main()
