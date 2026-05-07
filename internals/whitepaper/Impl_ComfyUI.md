# Python Implementation

## Examples of other node systems:

### Data-types

#### ComfyUI
has just a enumeration of data types:

https://github.com/comfyanonymous/ComfyUI/blob/master/comfy/comfy_types/node_typing.py

and it doesn't validate its adherence from node to node.

### Toplogical Sorting Implementations:

ComfyUI: https://github.com/comfyanonymous/ComfyUI/blob/master/comfy_execution/graph.py

### Custom nodes:

Definition of base classes and data types for custom nodes:
ComfyUI: https://github.com/comfyanonymous/ComfyUI/blob/master/comfy/comfy_types/node_typing.py

Example of implementation of custom nodes:
ComfyUI: https://github.com/comfyanonymous/ComfyUI/blob/master/custom_nodes/example_node.py.example

ComfyUI has a realtively simple way of defining a node:

* It defines the inputs, each identifiable by a name, through `def INPUT_TYPES(cls):`
  * with this functionit can calculate the values for the inputs, being enumerations for selections etc.
  * it returns a dictionary, separated by required and optional, of the inputs exposed through pins
    * containing the name, data type, and a default value.
    * this defines the values the executable function expects.
* It defines the name of the executable function
* It defines the outputs by creating a tuple with the datatypes
  * the executable function is expected to return this values in the exact order
* It defines the executable function
  * with its expected arguments
  * with the return values in a tuple following the structure defined for the outputs
* It allows the definition of VALIDATE_INPUTS method to check if the inputs are valid
* It allows the definition of IS_CHANGED to check if an input that doesn't come from another node (i.e. filesystem) has changed

Example
```python
class LoadVideo(ComfyNodeABC):
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["video"])
        return {"required":
                    {"file": (sorted(files), {"video_upload": True})},
                }

    CATEGORY = "image/video"

    RETURN_TYPES = (IO.VIDEO,)
    FUNCTION = "load_video"
    def load_video(self, file):
        video_path = folder_paths.get_annotated_filepath(file)
        return (VideoFromFile(video_path),)

    @classmethod
    def IS_CHANGED(cls, file):
        video_path = folder_paths.get_annotated_filepath(file)
        mod_time = os.path.getmtime(video_path)
        # Instead of hashing the file, we can just use the modification time to avoid
        # rehashing large files.
        return mod_time

    @classmethod
    def VALIDATE_INPUTS(cls, file):
        if not folder_paths.exists_annotated_filepath(file):
            return "Invalid video file: {}".format(file)

        return True
```
or here a more complicated example: https://github.com/comfyanonymous/ComfyUI/blob/0621d73a9c56fdc9e79aad87ed260135639bca50/nodes.py#L1518


### registering, finding and instantiating a node

#### ComfyUI

Module Import (__init__.py)

Location: custom_nodes/<node_package>/__init__.py
```python
# __init__.py is executed when Comfy attempts to import the module
NODE_CLASS_MAPPINGS = {
    "MyCustomNode": MyCustomNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MyCustomNode": "My Custom Node Display Name"
}
```

Process:

* ComfyUI scans the custom_nodes directory
* Imports each module's __init__.py
* Extracts NODE_CLASS_MAPPINGS to register available node classes
* Builds internal registry of available node types

---

Location: execution.py → Node class constructors
```python
# ComfyUI instantiates nodes as needed
class_type = node["class_type"]
class_def = nodes.NODE_CLASS_MAPPINGS[class_type]
obj = class_def()  # Node instance created
```
* Nodes are instantiated when first needed during execution
* Node __init__() method is called
* Instance is cached for reuse within the workflow

---

Location: execution.py → Node's main function

https://github.com/comfyanonymous/ComfyUI/blob/0621d73a9c56fdc9e79aad87ed260135639bca50/execution.py#L217C1-L234C1
```python
f = getattr(obj, func)
if inspect.iscoroutinefunction(f):
    async def async_wrapper(f, prompt_id, unique_id, list_index, args):
        with CurrentNodeContext(prompt_id, unique_id, list_index):
            return await f(**args)
    task = asyncio.create_task(async_wrapper(f, prompt_id, unique_id, index, args=inputs))
    # Give the task a chance to execute without yielding
    await asyncio.sleep(0)
    if task.done():
        result = task.result()
        results.append(result)
    else:
        results.append(task)
else:
    with CurrentNodeContext(prompt_id, unique_id, index):
        result = f(**inputs)
    results.append(result)
```
* `f = getattr(obj, func)` gets the function name that needs to be executed
* if the function has a `async` decorator, it is executed asynchronously
  * `async_wrapper` creates the instance of the function that can be executed asynchronously
  * `task = asyncio.create_task(` creates the task with the function and arguments
* otherwise it is a simple synchronous execution (which is almost always the case within comfyIU)

---

its not clear to me how comfyUI from here propagates the results to the output pins and then to the next nodes..

### Flow generation

#### ComfyUI

Location: execution.py → DynamicPrompt → ExecutionList

```python
# Workflow is converted to execution order
prompt = validate_prompt(workflow_json)
dynprompt = DynamicPrompt(prompt)
execution_list = dynprompt.get_execution_list()
```
