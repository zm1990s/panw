import { Hono } from "hono";
import { bearerAuth } from "hono/bearer-auth";
import { z } from "zod";
import { zValidator } from "@hono/zod-validator";
import { generateSchema } from '@anatine/zod-openapi';

type Bindings = {
  TOKEN: string;
};

const app = new Hono<{ Bindings: Bindings }>();

/*
const schema = z.object({
  point: z.any(), 
});
*/

const schema = z.object({
  point: z.union([
    z.literal("ping"),
    z.literal("app.external_data_tool.query"),
    z.literal("app.moderation.input"),
    z.literal("app.moderation.output"),
  ]), // Restricts 'point' to two specific values
  params: z
    .object({
      app_id: z.string().optional(),
      tool_variable: z.string().optional(),
      inputs: z.record(z.any()).optional(),
      query: z.any(),
      text: z.any()
    })
    .optional(),
});

// Generate OpenAPI schema
app.get("/", (c) => {
  return c.json(generateSchema(schema));
});

app.post(
  "/",
  (c, next) => {
    const auth = bearerAuth({ token: c.env.TOKEN });
    return auth(c, next);
  },
  zValidator("json", schema),
  async (c) => {
    const { point, params } = c.req.valid("json");
    if (point === "ping") {
      return c.json({
        result: "pong",
      });
    }
    // ⬇️ impliment your logic here ⬇️
    // point === "app.external_data_tool.query"
    else if (point === "app.moderation.input"){
    // 输入检查 ⬇️
    const userquery= params.query;
    const url = 'https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request';
    const headers = {
      'Content-Type': 'application/json',
      'x-pan-token': "PUTYOURTOKENHERE" 
    };
   
    const body = {
      metadata: {
        ai_model: "DifyAI model",
        app_name: "Dify Secure app",
        app_user: "Dify-user-1"
      },
      contents: [
        {
          prompt: userquery
        }
      ],
      ai_profile: {
        profile_name: "PUTYOURPROFILENAMEHERE"
      }
    };

    const result = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(body)
    }).then(res => res.text());
    /* debug PANW 接口返回 ⬇️
    return c.json({
      result
    });
    */
   let jsonResult = JSON.parse(result);
if ( jsonResult.action  === "block")
  {
    return c.json({
      "flagged": true,
      "action": "direct_output",
      "preset_response": "输入存在违法内容，请换个问题再试！"
    });
  }

else {
  return c.json({
    "flagged": false,
    "action": "direct_output",
    "preset_response": "输入无异常"
  });
};
    // 输入检查完毕 
    }
    
    else {
      // 输出检查 ⬇️
      const llmresponse= params.text;
      const url = 'https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request';
      const headers = {
        'Content-Type': 'application/json',
        'x-pan-token': "PUTYOURTOKENHERE" // Assuming you store the token in environment variables
      };
     
      const body = {
        metadata: {
          ai_model: "DifyAI model",
          app_name: "Dify Secure app",
          app_user: "Dify-user-1"
        },
        contents: [
          {
            response: llmresponse
          }
        ],
        ai_profile: {
          profile_name: "PUTYOURPROFILENAMEHERE"
        }
      };
  
      const result = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(body)
      }).then(res => res.text());
      /* debug PANW 接口返回 ⬇️
      return c.json({
        result
      });
      */
     let jsonResult = JSON.parse(result);
  if ( jsonResult.action  === "block")
    {
      return c.json({
        "flagged": true,
        "action": "direct_output",
        "preset_response": "输出存在敏感内容，已被系统过滤，请换个问题再问！"
      });
    }
  
  else {
    return c.json({
      "flagged": false,
      "action": "direct_output",
      "preset_response": "输出无异常"
    });
  };
    }

  }
);


export default app;
