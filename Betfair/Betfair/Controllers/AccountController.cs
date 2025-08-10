using Microsoft.AspNetCore.Mvc;
using Betfair.Services.Account;
using System.Threading.Tasks;

namespace Betfair.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class AccountController : ControllerBase
    {
        private readonly AccountService _accountService;

        public AccountController(AccountService accountService)
        {
            _accountService = accountService;
        }

        [HttpGet("funds")]
        public async Task<IActionResult> GetAccountFunds()
        {
            var accountFundsJson = await _accountService.GetAccountFundsAsync();
            return Content(accountFundsJson, "application/json");
        }
    }
}

